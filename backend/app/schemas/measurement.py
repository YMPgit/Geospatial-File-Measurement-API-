"""Pydantic schemas for per-feature measurement responses."""

from uuid import UUID

from pydantic import BaseModel, Field


class FeatureMeasurementResponse(BaseModel):
    """Measurement of a single feature inside an uploaded file."""

    feature_index: int
    geometry_type: str | None = None
    properties: dict = Field(default_factory=dict)
    measurement_type: str | None = None
    measurement_value: float | None = None
    measurement_unit: str | None = None
    measurement_status: str
    measurement_reason: str | None = None
    projected_crs: str | None = None
    geometry: dict | None = None


class MeasurementListResponse(BaseModel):
    """All measurements belonging to one file."""

    file_id: UUID
    filename: str
    file_type: str
    feature_count: int
    source_crs: str | None = None
    status: str
    measurements: list[FeatureMeasurementResponse]
