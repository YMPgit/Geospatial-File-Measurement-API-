"""KML phase-1 validation and GDAL-backed reading."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from defusedxml import ElementTree as SafeET

from app.core.exceptions import GeospatialProcessingError, InvalidArchiveError
from app.core.logging import get_logger

logger = get_logger(__name__)


def validate_kml(path: Path) -> None:
    """Phase-1 check: the upload must be well-formed XML with a <kml> root."""
    try:
        tree = SafeET.parse(str(path))
    except Exception as exc:
        raise InvalidArchiveError(f"KML file is not well-formed XML: {exc}") from exc
    root_tag = tree.getroot().tag.rsplit("}", 1)[-1]
    if root_tag.lower() != "kml":
        raise InvalidArchiveError("XML document does not have a <kml> root element.")


def read_kml(path: Path) -> gpd.GeoDataFrame:
    """Read the first (default) layer of a KML file with GDAL/pyogrio."""
    try:
        gdf = gpd.read_file(path, engine="pyogrio")
    except Exception as exc:
        logger.warning("GDAL failed to read KML %s: %s", path.name, exc)
        raise GeospatialProcessingError(f"Could not read KML file: {exc}") from exc
    return gdf
