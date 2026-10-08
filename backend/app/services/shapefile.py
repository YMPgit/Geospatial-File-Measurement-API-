"""Shapefile ZIP validation, safe extraction and GDAL-backed reading."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import geopandas as gpd

from app.core.exceptions import GeospatialProcessingError, InvalidArchiveError
from app.core.logging import get_logger
from app.utils.validators import validate_zip_safety

logger = get_logger(__name__)

REQUIRED_EXTENSIONS = (".shp", ".shx", ".dbf")
OPTIONAL_EXTENSIONS = (".prj",)
COMPANION_EXTENSIONS = REQUIRED_EXTENSIONS + OPTIONAL_EXTENSIONS


@dataclass(frozen=True)
class ShapefileSelection:
    """Deterministic choice of the shapefile components inside a ZIP."""

    shp_member: str
    members: dict[str, str] = field(default_factory=dict)  # ".shp" -> zip member name


def _group_members(infos: list[zipfile.ZipInfo]) -> dict[tuple[str, str], dict[str, str]]:
    """Group ZIP entries by (parent directory, lowercased stem) -> {ext: member}."""
    groups: dict[tuple[str, str], dict[str, str]] = {}
    for info in infos:
        normalized = info.filename.replace("\\", "/")
        path = PurePosixPath(normalized)
        stem = path.stem
        if not stem:
            continue
        key = (str(path.parent).lower(), stem.lower())
        groups.setdefault(key, {})[path.suffix.lower()] = normalized
    return groups


def validate_shapefile_zip(path: Path, max_total_bytes: int) -> ShapefileSelection:
    """Phase-1 check: structurally valid ZIP holding one readable shapefile."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise InvalidArchiveError("File is not a valid ZIP archive.") from exc

    with archive as zf:
        infos = validate_zip_safety(zf, max_total_bytes)
        groups = _group_members(infos)

        shp_members = sorted(
            exts[".shp"] for exts in groups.values() if ".shp" in exts
        )
        if not shp_members:
            raise InvalidArchiveError("ZIP archive does not contain a .shp file.")
        if len(shp_members) > 1:
            logger.warning(
                "ZIP %s contains %d shapefiles; using '%s' (lexicographically first).",
                path.name,
                len(shp_members),
                shp_members[0],
            )

        shp_member = shp_members[0]
        shp_path = PurePosixPath(shp_member)
        key = (str(shp_path.parent).lower(), shp_path.stem.lower())
        found = groups[key]

        missing = [ext for ext in REQUIRED_EXTENSIONS if ext not in found]
        if missing:
            raise InvalidArchiveError(
                f"ZIP archive is missing required Shapefile component(s): {', '.join(missing)}"
            )

        members = {ext: found[ext] for ext in COMPANION_EXTENSIONS if ext in found}
        return ShapefileSelection(shp_member=shp_member, members=members)


def extract_selection(archive_path: Path, selection: ShapefileSelection, dest_dir: Path) -> Path:
    """Extract only the selected components into ``dest_dir`` and return the .shp path.

    Extraction uses the member's basename only, so hostile member names can
    never escape ``dest_dir``.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        for member in selection.members.values():
            target = dest_dir / PurePosixPath(member).name
            with zf.open(member) as source, target.open("wb") as handle:
                while chunk := source.read(1024 * 1024):
                    handle.write(chunk)
    return dest_dir / PurePosixPath(selection.shp_member).name


def read_shapefile(shp_path: Path) -> gpd.GeoDataFrame:
    """Read an extracted .shp with GDAL/pyogrio (phase 2)."""
    try:
        return gpd.read_file(shp_path, engine="pyogrio")
    except Exception as exc:
        message = (str(exc) or exc.__class__.__name__).strip()
        # GDAL echoes the absolute extraction path back (e.g. Temp\\shp_extract_xyz\\broken.shp);
        # replace it with the bare filename so the user never sees internals.
        message = message.replace(str(shp_path), shp_path.name)
        logger.warning("GDAL failed to read shapefile %s: %s", shp_path.name, exc)
        raise GeospatialProcessingError(f"Could not read Shapefile: {message}") from exc
