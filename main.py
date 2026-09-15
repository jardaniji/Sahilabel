"""
main.py
-------
FastAPI backend for SAHILABEL.

Endpoints:
  POST /check         - upload an image, get back a JSON compliance report
  GET  /report/{id}/pdf - download the PDF for a previously-checked item
  GET  /history        - list all previously checked items (for the dashboard)
  GET  /                - serves the simple upload UI

Run with:
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import os
import uuid
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ocr_pipeline import extract_text
from compliance_checker import check_fields
from report_pdf import generate_pdf_report

# --- PLUGIN IMPORTS (new, additive only) ---
from plugins.scoring import compute_score
from plugins.highlighting import annotate_image
from plugins.explanations import build_full_explanation_set
from plugins.dashboard_stats import compute_dashboard_stats
from plugins.human_verification import materialize_report, validate_human_status

app = FastAPI(title="SAHILABEL")

UPLOAD_DIR = "uploads"
REPORT_DIR = "reports"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Simple in-memory history (swap for SQLite before final submission -
# this is fine for a hackathon demo, but resets on server restart)
HISTORY = []

# --- PLUGIN STORAGE (new, additive only) ---
# Kept separate from HISTORY/record dicts on purpose, so the existing
# /history endpoint's response shape never changes. Plugins look up
# what they need here by item_id.
_PLUGIN_STORE = {}  # item_id -> {"images": [{"evidence_image_path", "ocr_words", ...}]}


class HumanVerificationRequest(BaseModel):
    human_status: Literal["PASS", "FAIL", "UNABLE_TO_VERIFY"]
    note: str | None = None
    inspector_id: str | None = None


def _image_summary(image_id: str, filename: str, source: str, ocr_result: dict) -> dict:
    words = ocr_result["words"]
    confidences = [word["conf"] for word in words if word.get("conf") is not None]
    return {
        "image_id": image_id,
        "filename": filename,
        "source": source,
        "preprocessing": ocr_result["preprocessing"],
        "ocr_word_count": len(words),
        "average_ocr_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0.0,
    }


def _combined_ocr(image_records: list[dict]) -> dict:
    """Combine OCR evidence, preserving the source tag on every individual word."""
    words, text_parts = [], []
    for image in image_records:
        text_parts.append(image["ocr_text"])
        words.extend(image["ocr_words"])
    return {"full_text": "\n\n###\n\n".join(text_parts), "words": words}


def _get_image_plugin_data(item_id: str, image_id: str) -> dict:
    plugin_data = _PLUGIN_STORE.get(item_id)
    if not plugin_data:
        raise HTTPException(404, "No stored OCR data for this item")
    image = next((entry for entry in plugin_data["images"] if entry["image_id"] == image_id), None)
    if not image:
        raise HTTPException(404, "Image not found")
    return image


def _update_final_summary(record: dict) -> dict:
    view = materialize_report(record["report"], record["human_verifications"])
    record["final_overall_status"] = view["final_overall_status"]
    record["final_overall_compliant"] = view["final_overall_compliant"]
    return view


@app.post("/check")
async def check_label(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    image_sources: list[str] | None = Form(None),
    latitude: float = Form(None),   # Feature: Geotagged Inspections
    longitude: float = Form(None),  # optional - None if not sent/denied
    inspector_id: str = Form(None), # optional - wire up once auth exists
):
    uploads = ([file] if file is not None else []) + list(files or [])
    if not uploads:
        raise HTTPException(422, "Please upload at least one image file")
    for upload in uploads:
        if not (upload.content_type or "").startswith("image/"):
            raise HTTPException(400, "Please upload image files only")

    item_id = str(uuid.uuid4())[:8]
    inspection_images, plugin_images = [], []
    for index, upload in enumerate(uploads, start=1):
        image_id = f"image_{index:02d}"
        filename = upload.filename or f"{image_id}.jpg"
        ext = os.path.splitext(filename)[1] or ".jpg"
        image_path = os.path.join(UPLOAD_DIR, f"{item_id}_{image_id}{ext}")
        with open(image_path, "wb") as f:
            f.write(await upload.read())
        processed_path = os.path.join(PROCESSED_DIR, f"{item_id}_{image_id}.png")
        ocr_result = extract_text(image_path, processed_path=processed_path)
        source = (image_sources or [])[index - 1] if image_sources and index <= len(image_sources) else "upload"
        tagged_words = [{**word, "image_id": image_id, "source_filename": filename} for word in ocr_result["words"]]
        inspection_images.append(_image_summary(image_id, filename, source, {**ocr_result, "words": tagged_words}))
        plugin_images.append({
            "image_id": image_id, "filename": filename, "source": source,
            # OCR candidates retain original-image coordinates, so annotation
            # must be rendered on the original rather than a processed preview.
            "original_image_path": image_path, "evidence_image_path": image_path,
            "processed_image_path": processed_path if ocr_result["preprocessing"].get("processed_image_available") else None,
            "ocr_text": ocr_result["full_text"], "ocr_words": tagged_words,
        })

    report = check_fields(_combined_ocr(plugin_images))
    report_view = materialize_report(report)
    product_name = inspection_images[0]["filename"]

    pdf_path = os.path.join(REPORT_DIR, f"{item_id}.pdf")
    generate_pdf_report(report_view, product_name, pdf_path, inspection_images)

    record = {
        "id": item_id,
        "filename": product_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "overall_compliant": report["overall_compliant"],
        "location": (
            {"latitude": latitude, "longitude": longitude}
            if latitude is not None and longitude is not None else None
        ),
        "inspector_id": inspector_id,
        "report": report,
        "images": inspection_images,
        "image_count": len(inspection_images),
        "preprocessing": inspection_images[0]["preprocessing"] if len(inspection_images) == 1 else None,
        "human_verifications": {},
        "final_overall_status": report_view["final_overall_status"],
        "final_overall_compliant": report_view["final_overall_compliant"],
    }
    HISTORY.append(record)

    # PLUGIN: stash what scoring/highlighting/explanations will need,
    # without touching `record` or HISTORY's shape at all
    _PLUGIN_STORE[item_id] = {"images": plugin_images}

    return JSONResponse(record)


@app.get("/report/{item_id}/pdf")
async def download_pdf(item_id: str):
    pdf_path = os.path.join(REPORT_DIR, f"{item_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Report not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"compliance_{item_id}.pdf")


@app.get("/history")
async def get_history():
    # Return newest first, without the full report body (keep it light)
    return [
        {k: v for k, v in r.items() if k not in {"report", "human_verifications"}} for r in reversed(HISTORY)
    ]


# ============================================================
# NEW PLUGIN ENDPOINTS (Features 2, 3, 4, 8)
# None of these modify the routes above. Each is independently
# removable by deleting its @app.get/@app.post block below.
# ============================================================

def _find_record(item_id: str) -> dict:
    record = next((r for r in HISTORY if r["id"] == item_id), None)
    if not record:
        raise HTTPException(404, "Item not found")
    return record


@app.get("/score/{item_id}")
async def get_score(item_id: str):
    """Feature 3: Compliance Score"""
    record = _find_record(item_id)
    return compute_score(record["report"])


@app.get("/annotated/{item_id}")
async def get_annotated_image(item_id: str):
    """Feature 2: Violation Highlighting - returns the annotated image file"""
    record = _find_record(item_id)
    image = _get_image_plugin_data(item_id, "image_01")
    report_view = _update_final_summary(record)
    output_path = annotate_image(image["evidence_image_path"], image["ocr_words"], report_view, f"{item_id}_image_01", "image_01")
    return FileResponse(output_path, media_type="image/png")


@app.get("/annotated/{item_id}/{image_id}")
async def get_annotated_image_for_source(item_id: str, image_id: str):
    record = _find_record(item_id)
    image = _get_image_plugin_data(item_id, image_id)
    report_view = _update_final_summary(record)
    output_path = annotate_image(image["evidence_image_path"], image["ocr_words"], report_view, f"{item_id}_{image_id}", image_id)
    return FileResponse(output_path, media_type="image/png")


@app.get("/evidence/{item_id}/{image_id}/{variant}")
async def get_evidence_image(item_id: str, image_id: str, variant: Literal["original", "processed", "annotated"]):
    record = _find_record(item_id)
    image = _get_image_plugin_data(item_id, image_id)
    if variant == "annotated":
        report_view = _update_final_summary(record)
        path = annotate_image(image["evidence_image_path"], image["ocr_words"], report_view, f"{item_id}_{image_id}", image_id)
    elif variant == "processed":
        path = image.get("processed_image_path") or image["evidence_image_path"]
    else:
        path = image["original_image_path"]
    if not os.path.exists(path):
        raise HTTPException(404, "Evidence image not found")
    return FileResponse(path, media_type="image/png" if path.lower().endswith(".png") else "image/jpeg")


@app.put("/verification/{item_id}/rules/{rule_id}")
async def verify_rule(item_id: str, rule_id: str, verification: HumanVerificationRequest):
    record = _find_record(item_id)
    rule = next((entry for entry in record["report"].get("rules", []) if entry["rule_id"] == rule_id), None)
    if not rule:
        raise HTTPException(404, "Rule not found")
    automated_status = rule.get("automated_status", rule.get("status"))
    if automated_status != "REVIEW":
        raise HTTPException(409, "Human verification is available only for automated REVIEW rules")
    try:
        human_status = validate_human_status(verification.human_status)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record["human_verifications"][rule_id] = {
        "human_status": human_status,
        "note": verification.note,
        "inspector_id": verification.inspector_id or record.get("inspector_id"),
        "verified_at": datetime.now().isoformat(timespec="seconds"),
    }
    report_view = _update_final_summary(record)
    generate_pdf_report(report_view, record["filename"], os.path.join(REPORT_DIR, f"{item_id}.pdf"), record["images"])
    updated_rule = next(entry for entry in report_view["rules"] if entry["rule_id"] == rule_id)
    return {"item_id": item_id, "rule": updated_rule, "final_overall_status": report_view["final_overall_status"], "final_overall_compliant": report_view["final_overall_compliant"]}


@app.get("/explanations/{item_id}")
async def get_explanations(item_id: str):
    """Feature 8: AI Violation Explanation (template-based)"""
    record = _find_record(item_id)
    return build_full_explanation_set(record["report"])


@app.get("/dashboard/stats")
async def get_dashboard_stats():
    """Feature 4: Advanced Dashboard - aggregate stats, existing /history untouched"""
    return compute_dashboard_stats(HISTORY)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r") as f:
        return f.read()


app.mount("/static", StaticFiles(directory="static"), name="static")
