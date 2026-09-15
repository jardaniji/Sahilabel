# SAHILABEL

SAHILABEL is a local FastAPI application for reviewing packaged-commodity label images against a deterministic R01–R59 Legal Metrology checklist. It is being prepared for SIH 2026, problem statement PS 26034.

The application supports evidence-based review; it is not a substitute for legal advice, physical measurement, or external registration checks.

## Current implementation

- Python 3.12 PaddleOCR environment
- PaddlePaddle 3.2.0 and PaddleOCR 3.7.0
- OpenCV preprocessing with multiple OCR variants
- Multi-image inspections with `image_id`, source filename, OCR variant, OCR confidence, and word bounding boxes retained as evidence
- Deterministic structured extraction for manufacturer, product name, net quantity, MRP, MFG/PKD date, customer care, expiry/use-by/best-before, batch/lot number, and recognized declarations
- Field-level confidence calculated from each field's supporting OCR evidence, with unresolved/ambiguous states when contextual proof is insufficient
- A deterministic R01–R59 compliance engine that returns PASS, FAIL, REVIEW, or N/A as applicable
- Human verification kept separate from automated status
- Evidence annotations, PDF reports, in-memory inspection history, scoring, and dashboard summaries

No LLM, RAG system, or probabilistic rule engine is used. PaddleOCR is retained as the OCR engine.

## Requirements

Use the project-local Python 3.12 Paddle environment:

```powershell
.\.venv-paddle\Scripts\Activate.ps1
python -m pip install -r requirements-paddle.txt
```

`requirements-paddle.txt` pins PaddlePaddle 3.2.0 and PaddleOCR 3.7.0. OpenCV is used for preprocessing; FastAPI, Uvicorn, ReportLab, Pillow, and `python-multipart` support the application and reports.

## Run locally

```powershell
.\.venv-paddle\Scripts\Activate.ps1
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` in a browser. Inspection history is in memory and resets when the server restarts. The application creates local `uploads/`, `processed/`, `annotated/`, and `reports/` runtime directories as needed.

## Verification

```powershell
python -m unittest -v test_structured_extraction.py
python -m py_compile main.py ocr_pipeline.py compliance_checker.py structured_extraction.py
node --check static/app.js
```

The structured-extraction tests include contextual MRP, bare-price ambiguity, quantity, PKD/MFD, expiry, batch/lot, and 1-, 2-, and 4-image evidence cases.

## Repository hygiene

Runtime images, generated reports, model caches, virtual environments, local databases, logs, and Python caches are ignored. Do not commit uploaded package images or generated inspection evidence unless they are intentionally curated, consented test fixtures.

## Scope limits

Rules needing physical measurement, package classification, external registration, or facts unavailable from label images remain REVIEW or N/A. OCR can still miss or split printed text; SAHILABEL preserves the raw evidence and does not turn weak contextual evidence into a legal field value.
