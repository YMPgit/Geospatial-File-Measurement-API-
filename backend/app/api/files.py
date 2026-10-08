"""Endpoints for uploading and querying geospatial files."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ProcessingFailedError
from app.core.logging import get_logger
from app.db.database import get_db
from app.db.models import FeatureMeasurement, FileRecord
from app.schemas.file import (
    ErrorResponse,
    FileListResponse,
    FileResponse,
    FileUploadResponse,
)
from app.schemas.measurement import FeatureMeasurementResponse, MeasurementListResponse
from app.services.file_processor import process_upload
from app.utils.geometry import round_value

router = APIRouter(prefix="/api/files", tags=["files"])
logger = get_logger(__name__)

_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Validation failed or processing failed"},
    413: {"model": ErrorResponse, "description": "Upload exceeds the size limit"},
    422: {"model": ErrorResponse, "description": "Missing or malformed request body"},
    500: {"model": ErrorResponse, "description": "Unexpected server error"},
}


def _upload_body(record: FileRecord) -> dict:
    body = {
        "id": str(record.id),
        "filename": record.filename,
        "file_type": record.file_type,
        "feature_count": record.feature_count,
        "crs": record.source_crs,
        "status": record.status,
        "error_message": record.error_message,
    }
    if record.error_message is None:
        # Success responses carry exactly the documented keys.
        body.pop("error_message")
    return body


def _get_or_404(db: Session, file_id: uuid.UUID) -> FileRecord:
    record = db.get(FileRecord, file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return record


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=201,
    summary="Upload a KML or Shapefile ZIP and measure every feature",
    responses=_ERROR_RESPONSES,
)
@router.post(
    "",
    response_model=FileUploadResponse,
    status_code=201,
    include_in_schema=False,
)
def upload_file(
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File(description="A .kml file or a .zip containing a Shapefile")],
):
    """Validate, persist, read and measure an uploaded geospatial file."""
    try:
        record = process_upload(db, file.file, file.filename)
    except ProcessingFailedError as exc:
        # The record exists with status FAILED: return it with a 400.
        logger.warning("Upload of '%s' failed: %s", exc.record.filename, exc.detail)
        return JSONResponse(status_code=400, content=_upload_body(exc.record))
    # Returned as a raw JSON body so success carries exactly the documented keys
    # (response_model would re-add null optional fields).
    return JSONResponse(status_code=201, content=_upload_body(record))


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List uploaded files (newest first)",
)
@router.get("", response_model=FileListResponse, include_in_schema=False)
def list_files(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    total = db.scalar(select(func.count()).select_from(FileRecord)) or 0
    records = db.scalars(
        select(FileRecord)
        .order_by(FileRecord.created_at.desc(), FileRecord.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return FileListResponse(
        items=records,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{file_id}/",
    response_model=FileResponse,
    summary="Get file metadata",
    responses={404: {"model": ErrorResponse, "description": "Unknown file id"}},
)
@router.get(
    "/{file_id}",
    response_model=FileResponse,
    include_in_schema=False,
)
def get_file(file_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    return _get_or_404(db, file_id)


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementListResponse,
    summary="Get per-feature measurements for a file",
    responses={404: {"model": ErrorResponse, "description": "Unknown file id"}},
)
@router.get(
    "/{file_id}/measurements",
    response_model=MeasurementListResponse,
    include_in_schema=False,
)
def get_measurements(file_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    record = _get_or_404(db, file_id)
    rows = db.scalars(
        select(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == record.id)
        .order_by(FeatureMeasurement.feature_index)
    ).all()

    measurements = [
        FeatureMeasurementResponse(
            feature_index=row.feature_index,
            geometry_type=row.geometry_type,
            properties=row.properties or {},
            measurement_type=row.measurement_type,
            measurement_value=round_value(row.measurement_value),
            measurement_unit=row.measurement_unit,
            measurement_status=row.measurement_status,
            measurement_reason=row.measurement_reason,
            projected_crs=row.projected_crs,
            geometry=row.geometry,
        )
        for row in rows
    ]
    return MeasurementListResponse(
        file_id=record.id,
        filename=record.filename,
        file_type=record.file_type,
        feature_count=record.feature_count,
        source_crs=record.source_crs,
        status=record.status,
        measurements=measurements,
    )


@router.delete(
    "/{file_id}/",
    status_code=204,
    summary="Delete a file, its measurements and the stored original",
    responses={404: {"model": ErrorResponse, "description": "Unknown file id"}},
)
@router.delete(
    "/{file_id}",
    status_code=204,
    include_in_schema=False,
)
def delete_file(file_id: uuid.UUID, db: Annotated[Session, Depends(get_db)]):
    """Remove an uploaded file, its per-feature measurements and the stored original."""
    record = _get_or_404(db, file_id)
    stored_path = settings.upload_path / record.stored_filename

    # ORM cascade ("all, delete-orphan") removes the measurements alongside the record.
    db.delete(record)
    db.commit()

    try:
        stored_path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove stored file for %s", record.id)
