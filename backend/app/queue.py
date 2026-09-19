from __future__ import annotations

import json
from typing import Any

from redis import Redis

from app.config import settings


redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_analysis(payload: dict[str, Any]) -> str:
    job_id = payload["inspection_id"]
    redis_client.rpush("sahilabel:analysis", json.dumps(payload))
    redis_client.setex(f"sahilabel:job:{job_id}", 3600, json.dumps({"status": "QUEUED", "inspection_id": job_id}))
    return job_id


def get_job_status(job_id: str) -> dict[str, Any] | None:
    value = redis_client.get(f"sahilabel:job:{job_id}")
    return json.loads(value) if value else None
