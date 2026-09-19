from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    product_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    image_count: Mapped[int] = mapped_column(Integer, default=1)
    overall_compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


engine = create_engine(settings.postgres_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def save_inspection(record: dict[str, Any]) -> None:
    import json

    with SessionLocal() as session:
        row = session.query(Inspection).filter_by(inspection_id=record["inspection_id"]).one_or_none()
        if row is None:
            row = Inspection(
                inspection_id=record["inspection_id"],
                product_name=record.get("product_name", "Uploaded label"),
                image_count=record.get("image_count", 1),
            )
            session.add(row)
        row.status = record.get("status", "REVIEW")
        row.overall_compliant = bool(record.get("analysis", {}).get("overall_compliant", False))
        row.report_json = json.dumps(record, default=str)
        session.commit()


def get_inspection(inspection_id: str) -> dict[str, Any] | None:
    import json

    with SessionLocal() as session:
        row = session.query(Inspection).filter_by(inspection_id=inspection_id).one_or_none()
        if row is None:
            return None
        return json.loads(row.report_json) if row.report_json else {
            "inspection_id": row.inspection_id,
            "product_name": row.product_name,
            "status": row.status,
            "image_count": row.image_count,
        }
