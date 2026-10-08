"""ORM models for uploaded files and per-feature measurements."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

JSON_COLUMN = JSON().with_variant(JSONB(), "postgresql")


class FileStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MeasurementStatus(str, enum.Enum):
    CALCULATED = "CALCULATED"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    UNAVAILABLE = "UNAVAILABLE"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FileRecord(Base):
    """One row per uploaded file (KML or Shapefile ZIP)."""

    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_crs: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=FileStatus.PROCESSING.value)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    measurements: Mapped[list["FeatureMeasurement"]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureMeasurement.feature_index",
    )

    @property
    def status_value(self) -> str:
        return FileStatus(self.status).value


class FeatureMeasurement(Base):
    """Per-feature geometry, properties and measurement result."""

    __tablename__ = "feature_measurements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geometry: Mapped[dict | None] = mapped_column(JSON_COLUMN, nullable=True)
    properties: Mapped[dict] = mapped_column(JSON_COLUMN, nullable=False, default=dict)
    source_crs: Mapped[str | None] = mapped_column(String(128), nullable=True)
    measurement_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    measurement_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    measurement_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    measurement_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MeasurementStatus.UNAVAILABLE.value
    )
    measurement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    projected_crs: Mapped[str | None] = mapped_column(String(128), nullable=True)

    file: Mapped[FileRecord] = relationship(back_populates="measurements")
