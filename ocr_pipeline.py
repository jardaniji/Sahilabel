"""PaddleOCR adapter with conservative, provenance-preserving merging."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from computer_vision.preprocessor import build_ocr_variants, preprocess_for_ocr


# Keep Paddle's model cache local to this project. Paddle 3.2 imports an
# optional dataset module which otherwise writes to ~/.cache/paddle on import.
_PROJECT_ROOT = Path(__file__).resolve().parent
os.environ["HOME"] = str(_PROJECT_ROOT)
os.environ["USERPROFILE"] = str(_PROJECT_ROOT)
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(_PROJECT_ROOT / ".paddlex"))


@lru_cache(maxsize=1)
def _ocr_engine():
    """Load one CPU OCR engine and reuse it for all images and variants."""
    from paddleocr import PaddleOCR

    # Label photography is normally upright. OpenCV variants remain the
    # preprocessing strategy, so document-preprocessing models are unnecessary.
    return PaddleOCR(
        lang="en",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def _iou(left: dict, right: dict) -> float:
    x0, y0 = max(left["left"], right["left"]), max(left["top"], right["top"])
    x1 = min(left["left"] + left["width"], right["left"] + right["width"])
    y1 = min(left["top"] + left["height"], right["top"] + right["height"])
    overlap = max(0, x1 - x0) * max(0, y1 - y0)
    union = left["width"] * left["height"] + right["width"] * right["height"] - overlap
    return overlap / union if union else 0.0


def _ocr_variant(name: str, image) -> list[dict]:
    """Run PaddleOCR once and normalize its word evidence contract."""
    if isinstance(image, Image.Image):
        image = np.array(image.convert("RGB"))
    elif image.ndim == 2:
        # OpenCV enhancement variants are grayscale but Paddle's detector
        # expects a three-channel image.
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    result = next(iter(_ocr_engine().predict(image)), None)
    if result is None:
        return []
    payload = result.json.get("res", {})
    words = []
    for text, score, box in zip(
        payload.get("rec_texts", []),
        payload.get("rec_scores", []),
        payload.get("rec_boxes", []),
    ):
        text = str(text).strip()
        if not text or len(box) != 4:
            continue
        left, top, right, bottom = (int(value) for value in box)
        # Paddle returns 0..1 scores; the existing contract uses 0..100.
        confidence = max(0.0, min(100.0, float(score) * 100.0))
        words.append({
            "text": text, "conf": confidence, "left": left, "top": top,
            "width": max(1, right - left), "height": max(1, bottom - top),
            "variant": name,
        })
    return words


def _merge_words(candidates: list[dict]) -> list[dict]:
    """Deduplicate alternate readings of the same OCR region."""
    retained: list[dict] = []
    for word in sorted(candidates, key=lambda item: item["conf"], reverse=True):
        def same_region(existing: dict) -> bool:
            intersection = max(0, min(word["left"] + word["width"], existing["left"] + existing["width"]) - max(word["left"], existing["left"])) * max(0, min(word["top"] + word["height"], existing["top"] + existing["height"]) - max(word["top"], existing["top"]))
            smaller = min(word["width"] * word["height"], existing["width"] * existing["height"])
            return _iou(word, existing) >= 0.60 or (smaller and intersection / smaller >= 0.82)
        if not any(same_region(existing) for existing in retained):
            retained.append(word)
    return sorted(retained, key=lambda item: (item["top"] // max(1, item["height"]), item["left"]))


def _full_text(words: list[dict]) -> str:
    lines: list[list[dict]] = []
    for word in words:
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > max(word["height"], lines[-1][0]["height"]):
            lines.append([word])
        else:
            lines[-1].append(word)
    return "\n".join(" ".join(entry["text"] for entry in sorted(line, key=lambda item: item["left"])) for line in lines)


def extract_text(image_path: str, use_preprocessing: bool = True, processed_path: str | None = None) -> dict:
    """Extract merged PaddleOCR evidence while preserving OCR/image provenance."""
    evidence_image_path = image_path
    preprocessing = {"operations": ["Original retained"], "warnings": [], "used_fallback": False, "geometry_changed": False, "processed_image_available": False, "variants": ["original"]}
    try:
        if use_preprocessing:
            variants, preprocessing = build_ocr_variants(image_path)
            if processed_path:
                _, saved_metadata = preprocess_for_ocr(image_path, processed_path)
                preprocessing.update(saved_metadata)
                evidence_image_path = processed_path
        else:
            original = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if original is None:
                raise ValueError("OpenCV could not read image")
            variants = [("original", cv2.cvtColor(original, cv2.COLOR_BGR2RGB))]
    except Exception as exc:
        preprocessing["warnings"] = [f"Image enhancement was unavailable; the original image was used ({exc.__class__.__name__})."]
        preprocessing["used_fallback"] = True
        variants = [("original", Image.open(image_path).convert("RGB"))]

    all_words = []
    for name, image in variants:
        all_words.extend(_ocr_variant(name, image))
    preprocessing["ocr_passes"] = len(variants)
    words = _merge_words(all_words)
    return {"full_text": _full_text(words), "words": words, "preprocessing": preprocessing, "evidence_image_path": evidence_image_path}
