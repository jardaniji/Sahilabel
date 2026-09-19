"""FastAPI backend for SAHILABEL."""

import os
import uuid
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import require_role, router as auth_router
from compliance_checker import check_fields
from ocr_pipeline import extract_text
from report_pdf import generate_pdf_report
from review_api import review_router
from plugins.dashboard_stats import compute_dashboard_stats
from plugins.explanations import build_full_explanation_set
from plugins.highlighting import annotate_image
from plugins.human_verification import materialize_report, validate_human_status
from plugins.scoring import compute_score

app = FastAPI(title="SAHILABEL")
app.include_router(auth_router)
app.include_router(review_router)

UPLOAD_DIR = "uploads"
REPORT_DIR = "reports"
PROCESSED_DIR = "processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

HISTORY: list[dict] = []
_PLUGIN_STORE: dict[str, dict] = {}
INSPECTIONS: dict[str, dict] = {}
WORKFLOW = "Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Inspector Review -> Final Report"


class HumanVerificationRequest(BaseModel):
    human_status: Literal["PASS", "FAIL", "UNABLE_TO_VERIFY"]
    note: str | None = None
    inspector_id: str | None = None


class InspectionCreateRequest(BaseModel):
    product_name: str
    image_count: int = 1
    source: str = "upload"


class InspectionStatusResponse(BaseModel):
    inspection_id: str
    status: str
    product_name: str
    image_count: int
    workflow: str = WORKFLOW


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


def _find_record(item_id: str) -> dict:
    record = next((r for r in HISTORY if r["id"] == item_id), None)
    if not record:
        raise HTTPException(404, "Item not found")
    return record


def _update_final_summary(record: dict) -> dict:
    view = materialize_report(record["report"], record["human_verifications"])
    record["final_overall_status"] = view["final_overall_status"]
    record["final_overall_compliant"] = view["final_overall_compliant"]
    return view


@app.get("/health")
async def healthcheck() -> dict:
    return {"status": "ok", "app": "SAHILABEL", "workflow": WORKFLOW}


@app.get("/api/v1/status")
async def status_summary() -> dict:
    return {"status": "ok", "architecture_phase": "phase-2-production-backend", "workflow": WORKFLOW}


@app.post("/api/v1/inspections", response_model=InspectionStatusResponse)
async def create_inspection(payload: InspectionCreateRequest, user: dict = Depends(require_role("admin", "inspector"))) -> dict:
    inspection_id = f"insp-{uuid.uuid4().hex[:10]}"
    record = {
        "inspection_id": inspection_id,
        "product_name": payload.product_name.strip() or "Uploaded label",
        "image_count": max(1, min(payload.image_count, 8)),
        "status": "QUEUED",
        "source": payload.source,
        "created_by": user["username"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workflow": WORKFLOW,
    }
    INSPECTIONS[inspection_id] = record
    return record


@app.get("/api/v1/inspections")
async def list_inspections(user: dict = Depends(require_role("admin", "inspector", "viewer"))) -> list[dict]:
    return list(INSPECTIONS.values())


@app.get("/api/v1/inspections/{inspection_id}/status")
async def get_inspection_status(inspection_id: str, user: dict = Depends(require_role("admin", "inspector", "viewer"))) -> dict:
    record = INSPECTIONS.get(inspection_id)
    if not record:
        raise HTTPException(404, "Inspection not found")
    return record


@app.post("/check")
async def check_label(
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    image_sources: list[str] | None = Form(None),
    latitude: float = Form(None),
    longitude: float = Form(None),
    inspector_id: str = Form(None),
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
        with open(image_path, "wb") as output:
            output.write(await upload.read())
        processed_path = os.path.join(PROCESSED_DIR, f"{item_id}_{image_id}.png")
        ocr_result = extract_text(image_path, processed_path=processed_path)
        source = (image_sources or [])[index - 1] if image_sources and index <= len(image_sources) else "upload"
        tagged_words = [{**word, "image_id": image_id, "source_filename": filename} for word in ocr_result["words"]]
        inspection_images.append(_image_summary(image_id, filename, source, {**ocr_result, "words": tagged_words}))
        plugin_images.append({
            "image_id": image_id,
            "filename": filename,
            "source": source,
            "original_image_path": image_path,
            "evidence_image_path": image_path,
            "processed_image_path": processed_path if ocr_result["preprocessing"].get("processed_image_available") else None,
            "ocr_text": ocr_result["full_text"],
            "ocr_words": tagged_words,
        })

    report = check_fields(_combined_ocr(plugin_images))
    report_view = materialize_report(report)
    product_name = inspection_images[0]["filename"]
    generate_pdf_report(report_view, product_name, os.path.join(REPORT_DIR, f"{item_id}.pdf"), inspection_images)

    record = {
        "id": item_id,
        "filename": product_name,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "overall_compliant": report["overall_compliant"],
        "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
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
    _PLUGIN_STORE[item_id] = {"images": plugin_images}
    INSPECTIONS[item_id] = {
        "inspection_id": item_id,
        "product_name": product_name,
        "status": report_view["final_overall_status"],
        "image_count": len(inspection_images),
        "workflow": WORKFLOW,
    }
    return JSONResponse(record)


@app.get("/report/{item_id}/pdf")
async def download_pdf(item_id: str):
    pdf_path = os.path.join(REPORT_DIR, f"{item_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(404, "Report not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"compliance_{item_id}.pdf")


@app.get("/history")
async def get_history():
    return [{k: v for k, v in r.items() if k not in {"report", "human_verifications"}} for r in reversed(HISTORY)]


@app.get("/score/{item_id}")
async def get_score(item_id: str):
    return compute_score(_find_record(item_id)["report"])


@app.get("/annotated/{item_id}")
async def get_annotated_image(item_id: str):
    record = _find_record(item_id)
    image = _get_image_plugin_data(item_id, "image_01")
    return FileResponse(
        annotate_image(image["evidence_image_path"], image["ocr_words"], _update_final_summary(record), f"{item_id}_image_01", "image_01"),
        media_type="image/png",
    )


@app.get("/annotated/{item_id}/{image_id}")
async def get_annotated_image_for_source(item_id: str, image_id: str):
    record = _find_record(item_id)
    image = _get_image_plugin_data(item_id, image_id)
    output_path = annotate_image(image["evidence_image_path"], image["ocr_words"], _update_final_summary(record), f"{item_id}_{image_id}", image_id)
    return FileResponse(output_path, media_type="image/png")


@app.get("/evidence/{item_id}/{image_id}/{variant}")
async def get_evidence_image(item_id: str, image_id: str, variant: Literal["original", "processed", "annotated"]):
    record = _find_record(item_id)
    image = _get_image_plugin_data(item_id, image_id)
    if variant == "annotated":
        path = annotate_image(image["evidence_image_path"], image["ocr_words"], _update_final_summary(record), f"{item_id}_{image_id}", image_id)
    elif variant == "processed":
        path = image.get("processed_image_path") or image["evidence_image_path"]
    else:
        path = image["original_image_path"]
    if not os.path.exists(path):
        raise HTTPException(404, "Evidence image not found")
    return FileResponse(path, media_type="image/png" if path.lower().endswith(".png") else "image/jpeg")


@app.put("/verification/{item_id}/rules/{rule_id}")
async def verify_rule(item_id: str, rule_id: str, verification: HumanVerificationRequest, user: dict = Depends(require_role("admin", "inspector"))):
    record = _find_record(item_id)
    rule = next((entry for entry in record["report"].get("rules", []) if entry["rule_id"] == rule_id), None)
    if not rule:
        raise HTTPException(404, "Rule not found")
    if rule.get("automated_status", rule.get("status")) != "REVIEW":
        raise HTTPException(409, "Human verification is available only for automated REVIEW rules")
    try:
        human_status = validate_human_status(verification.human_status)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record["human_verifications"][rule_id] = {
        "human_status": human_status,
        "note": verification.note,
        "inspector_id": user["username"],
        "verified_at": datetime.now().isoformat(timespec="seconds"),
    }
    report_view = _update_final_summary(record)
    generate_pdf_report(report_view, record["filename"], os.path.join(REPORT_DIR, f"{item_id}.pdf"), record["images"])
    return {"item_id": item_id, "final_overall_status": report_view["final_overall_status"], "final_overall_compliant": report_view["final_overall_compliant"]}


@app.get("/explanations/{item_id}")
async def get_explanations(item_id: str):
    return build_full_explanation_set(_find_record(item_id)["report"])


@app.get("/dashboard/stats")
async def get_dashboard_stats(user: dict = Depends(require_role("inspector", "admin"))):
    return compute_dashboard_stats(HISTORY)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r") as input_file:
        return input_file.read()


app.mount("/static", StaticFiles(directory="static"), name="static")
