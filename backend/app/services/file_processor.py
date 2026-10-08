"""End-to-end upload pipeline: validate -> record -> read -> measure -> persist."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import BinaryIO

import geopandas as gpd
from shapely.geometry.base import BaseGeometry
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import GeospatialProcessingError, ProcessingFailedError
from app.core.logging import get_logger
from app.db.models import FeatureMeasurement, FileRecord, FileStatus
from app.services import kml as kml_service
from app.services import shapefile as shapefile_service
from app.services.crs import describe_crs
from app.services.measurement import measure_geometry
from app.utils import validators
from app.utils.geometry import clean_properties, geometry_to_geojson

logger = get_logger(__name__)

_ERROR_MESSAGE_LIMIT = 2000


def process_upload(db: Session, stream: BinaryIO, original_filename: str | None) -> FileRecord:
    """Run the whole upload pipeline.

    Phase 1 (extension, size, archive structure, XML well-formedness) rejects
    with 400/413 and creates **no** record. Phase 2 (GDAL read / measurement)
    always persists a record: COMPLETED on success, FAILED on failure.
    """
    # ---- Phase 1: reject before any DB record exists -----------------------
    filename = validators.sanitize_filename(original_filename)
    extension = validators.allowed_extension(filename)
    file_type = "kml" if extension == ".kml" else "shapefile"

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    destination = settings.upload_path / stored_filename
    validators.save_upload(stream, destination, settings.max_upload_size_bytes)

    payload: dict = {"file_type": file_type}
    try:
        if file_type == "kml":
            kml_service.validate_kml(destination)
        else:
            max_total = settings.max_upload_size_bytes * validators.MAX_ZIP_UNCOMPRESSED_MULTIPLIER
            payload["selection"] = shapefile_service.validate_shapefile_zip(destination, max_total)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

    # ---- Phase 2: from here on, a record always exists ---------------------
    record = FileRecord(
        filename=filename,
        stored_filename=stored_filename,
        file_type=file_type,
        feature_count=0,
        source_crs=None,
        status=FileStatus.PROCESSING.value,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        gdf = _read_geodataframe(destination, payload)
        _measure_and_persist(db, record, gdf)
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        _mark_failed(db, record, detail)
        raise ProcessingFailedError(record, detail) from exc

    db.refresh(record)
    return record


def _read_geodataframe(destination: Path, payload: dict) -> gpd.GeoDataFrame:
    if payload["file_type"] == "kml":
        return kml_service.read_kml(destination)
    selection = payload["selection"]
    with tempfile.TemporaryDirectory(prefix="shp_extract_") as tmp:
        shp_path = shapefile_service.extract_selection(destination, selection, Path(tmp))
        return shapefile_service.read_shapefile(shp_path)


def _measure_and_persist(db: Session, record: FileRecord, gdf: gpd.GeoDataFrame) -> None:
    if gdf is None or len(gdf) == 0:
        raise GeospatialProcessingError("File contains no features to measure.")

    source_crs = gdf.crs
    source_label = describe_crs(source_crs) if source_crs is not None else None
    geometry_column = gdf.geometry.name

    measurements: list[FeatureMeasurement] = []
    for index, (_, row) in enumerate(gdf.iterrows()):
        attributes = row.to_dict()
        geom: BaseGeometry | None = attributes.pop(geometry_column, None)

        outcome = measure_geometry(geom, source_crs)
        measurements.append(
            FeatureMeasurement(
                file_id=record.id,
                feature_index=index,
                geometry_type=geom.geom_type if geom is not None else None,
                geometry=geometry_to_geojson(geom),
                properties=clean_properties(attributes),
                source_crs=source_label,
                measurement_type=outcome.measurement_type,
                measurement_value=outcome.measurement_value,
                measurement_unit=outcome.measurement_unit,
                measurement_status=outcome.measurement_status,
                measurement_reason=outcome.measurement_reason,
                projected_crs=outcome.projected_crs,
            )
        )

    record.feature_count = len(measurements)
    record.source_crs = source_label
    record.status = FileStatus.COMPLETED.value
    record.error_message = None
    db.add_all(measurements)
    db.commit()


def _mark_failed(db: Session, record: FileRecord, detail: str) -> None:
    record.status = FileStatus.FAILED.value
    record.error_message = detail[:_ERROR_MESSAGE_LIMIT]
    try:
        db.commit()
    except Exception:
        logger.exception("Could not persist FAILED status for file %s", record.id)
        db.rollback()
    logger.warning("Processing failed for '%s' (%s): %s", record.filename, record.id, detail)
