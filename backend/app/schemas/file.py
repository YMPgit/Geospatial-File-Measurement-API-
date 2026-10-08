"""Pydantic schemas for file upload, file info and list responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FileUploadResponse(BaseModel):
    """Response returned by POST /api/files/."""

    id: UUID
    filename: str
    file_type: str
    feature_count: int
    crs: str | None = None
    status: str
    error_message: str | None = None


class FileResponse(BaseModel):
    """Response returned by GET /api/files/{file_id}/."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_type: str
    feature_count: int
    source_crs: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class FileListItem(BaseModel):
    """Summary row used by the dashboard recent-files list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_type: str
    feature_count: int
    source_crs: str | None = None
    status: str
    created_at: datetime


class FileListResponse(BaseModel):
    """Paginated list of uploaded files."""

    items: list[FileListItem]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    """Standard error body produced by the API."""

    detail: str = Field(examples=["Unsupported file type. Allowed: .kml, .zip"])
