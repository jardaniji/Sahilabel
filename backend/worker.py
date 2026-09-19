from __future__ import annotations

import json
import logging

from app.db import init_db, save_inspection
from app.queue import redis_client
from app.services.inspection_store import get_inspection_record
from app.services.workflow_service import WorkflowService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sahilabel.worker")


def run_worker() -> None:
    init_db()
    logger.info("SAHILABEL analysis worker started")
    while True:
        _, raw = redis_client.blpop("sahilabel:analysis")
        payload = json.loads(raw)
        inspection_id = payload["inspection_id"]
        try:
            result = WorkflowService.process_image(payload["image_path"], inspection_id)
            record = get_inspection_record(inspection_id)
            record.update(result)
            save_inspection(record)
            redis_client.setex(
                f"sahilabel:job:{inspection_id}",
                3600,
                json.dumps({"status": result.get("status", "REVIEW"), "inspection_id": inspection_id}),
            )
        except Exception as exc:  # keep worker alive for later jobs
            logger.exception("Analysis failed for %s", inspection_id)
            redis_client.setex(
                f"sahilabel:job:{inspection_id}",
                3600,
                json.dumps({"status": "FAILED", "inspection_id": inspection_id, "error": str(exc)}),
            )


if __name__ == "__main__":
    run_worker()
