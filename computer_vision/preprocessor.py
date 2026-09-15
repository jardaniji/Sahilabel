"""Conservative, failure-tolerant label-image preprocessing for OCR."""

from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np


def _safe_step(work: np.ndarray, metadata: dict[str, Any], name: str, operation):
    """Run one optional transformation without sacrificing an otherwise usable scan."""
    try:
        candidate = operation(work)
        if candidate is not None and candidate.shape == work.shape:
            metadata["operations"].append(name)
            return candidate
    except Exception as exc:  # OCR must continue even if an enhancement cannot run.
        metadata["warnings"].append(f"{name} was skipped: {exc.__class__.__name__}")
    return work


def _needs_contrast_enhancement(gray: np.ndarray) -> bool:
    return float(np.std(gray)) < 58.0


def _has_visible_noise(gray: np.ndarray) -> bool:
    """Estimate high-frequency noise conservatively to avoid softening small print."""
    residual = cv2.absdiff(gray, cv2.GaussianBlur(gray, (3, 3), 0))
    return float(np.median(residual)) >= 7.0


def _has_uneven_lighting(gray: np.ndarray) -> bool:
    small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    return float(np.std(small)) >= 30.0


def _reduce_small_glare(gray: np.ndarray) -> np.ndarray | None:
    """Suppress only small, isolated specular highlights; never inpaint broad white label areas."""
    mask = cv2.inRange(gray, 248, 255)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    safe_mask = np.zeros_like(mask)
    image_area = gray.shape[0] * gray.shape[1]
    for label in range(1, count):
        x, y, width, height, area = stats[label]
        # Broad bright regions are normally label background, not reliable glare targets.
        if 12 <= area <= max(80, int(image_area * 0.004)) and x > 0 and y > 0 and x + width < gray.shape[1] and y + height < gray.shape[0]:
            safe_mask[labels == label] = 255
    if not np.any(safe_mask):
        return None
    return cv2.inpaint(gray, safe_mask, 3, cv2.INPAINT_TELEA)


def _deskew(gray: np.ndarray) -> tuple[np.ndarray, float] | None:
    """Return a same-canvas deskewed image only for a modest, confidently detected angle."""
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return None
    angle = cv2.minAreaRect(coords.astype(np.float32))[1]
    correction = -(90.0 + angle) if angle < -45.0 else -angle
    if not 0.4 <= abs(correction) <= 8.0:
        return None
    height, width = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), correction, 1.0)
    rotated = cv2.warpAffine(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, correction


def build_ocr_variants(image_path: str) -> tuple[list[tuple[str, np.ndarray]], dict[str, Any]]:
    """Return a small, diagnostics-driven set of same-geometry OCR candidates.

    Coordinates from every candidate remain valid for the original image.  This
    matters because OCR boxes are also used as audit evidence; therefore this
    function deliberately avoids rotation, cropping, and rescaling.
    """
    source = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if source is None:
        raise ValueError(f"OpenCV could not read image at '{image_path}'.")

    metadata: dict[str, Any] = {
        "operations": ["Original retained", "Grayscale conversion"],
        "warnings": [],
        "used_fallback": False,
        "geometry_changed": False,
    }
    gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
    # Keep an unmodified RGB candidate; all other candidates retain identical
    # width/height so their OCR boxes share the same coordinate system.
    variants: list[tuple[str, np.ndarray]] = [("original", cv2.cvtColor(source, cv2.COLOR_BGR2RGB))]
    contrast_needed = _needs_contrast_enhancement(gray)
    uneven_lighting = _has_uneven_lighting(gray)
    noisy = _has_visible_noise(gray)

    enhanced = gray
    if contrast_needed or uneven_lighting:
        enhanced = _safe_step(gray, metadata, "CLAHE contrast enhancement", lambda image: cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(image))
        if not np.array_equal(enhanced, gray):
            variants.append(("clahe", enhanced))

    if noisy:
        denoised = _safe_step(enhanced, metadata, "Careful noise reduction", lambda image: cv2.fastNlMeansDenoising(image, None, 7, 7, 21))
        if not np.array_equal(denoised, enhanced):
            variants.append(("denoised", denoised))

    if uneven_lighting:
        threshold_source = enhanced if not np.array_equal(enhanced, gray) else gray
        thresholded = _safe_step(threshold_source, metadata, "Adaptive threshold", lambda image: cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11))
        if not np.array_equal(thresholded, threshold_source):
            variants.append(("adaptive_threshold", thresholded))

    metadata["variants"] = [name for name, _ in variants]
    return variants[:4], metadata


def preprocess_for_ocr(image_path: str, output_path: str | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Build and optionally persist the preferred separate OCR-ready image.

    ``build_ocr_variants`` is the OCR entry point; this compatibility wrapper
    still provides the historic single processed file for the evidence route.
    """
    variants, metadata = build_ocr_variants(image_path)
    # Prefer thresholded/contrast candidates for the saved processing preview,
    # while the OCR pipeline evaluates all candidates including the original.
    work = variants[-1][1]

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        if not cv2.imwrite(output_path, work):
            raise ValueError(f"Could not write processed image to '{output_path}'.")
        metadata["processed_image_available"] = True
    else:
        metadata["processed_image_available"] = False
    return work, metadata
