# Phase 1 architecture integration

This branch adds a non-breaking architecture layer around the existing OCR and compliance engine.

## Run the existing application

```bash
python -m pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Run the new backend API

From the repository root:

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

The new API is available at:

- `GET /health`
- `POST /api/v1/auth/login`
- `POST /api/v1/inspections`
- `POST /api/v1/inspections/analyze`
- `GET /api/v1/inspections/{inspection_id}`

Example image analysis request:

```bash
curl -X POST http://localhost:8000/api/v1/inspections/analyze \
  -F "product_name=Sample label" \
  -F "file=@path/to/label.jpg"
```

The analysis endpoint now follows this sequence:

```text
Input -> Image Quality -> CV/OCR -> Applicability -> Rule Validation -> Review
```

The original `main.py` application remains available while this migration is being completed.

## Run the React frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and calls the new API at `http://localhost:8000`.

## Start PostgreSQL and Redis locally

```bash
docker compose up -d postgres redis
```

The current workflow API still uses an in-memory compatibility store. PostgreSQL persistence and Redis worker processing are the next migration step; no existing inspection data is changed by this phase.
