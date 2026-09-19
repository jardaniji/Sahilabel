# Production-backend phase

The feature branch now includes:

- SQLAlchemy persistence with PostgreSQL-compatible configuration
- Redis queue adapter
- A separate worker process for OCR/compliance analysis
- Persistent inspection status and report JSON
- Real multipart image upload handling with a 15 MB limit
- Graceful local fallback when PostgreSQL or Redis is not running

Start infrastructure:

```bash
docker compose up -d postgres redis
```

Install backend dependencies and start the API:

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal, start the worker:

```bash
python -m backend.worker
```

Start the React frontend in a third terminal:

```bash
cd frontend
npm install
npm run dev
```

The upload endpoint is:

```text
POST /api/v1/inspections/analyze
```

The worker processes the queued image and updates the inspection status. The API remains usable without Docker for simple development, but PostgreSQL and Redis should be running for persistence and asynchronous processing.

Do not commit a real `.env` file or production JWT secret. Copy `.env.example` to `.env` and replace the development values locally.
