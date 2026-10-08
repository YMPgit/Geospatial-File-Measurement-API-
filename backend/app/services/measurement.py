"""Per-feature area/length measurement dispatch."""

from __future__ import annotations

from dataclasses import dataclass

from pyproj import CRS, Transformer
from shapely import make_valid
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

from app.db.models import MeasurementStatus
from app.services.crs import choose_measurement_crs, describe_crs, metre_factor, parse_crs

AREA_TYPES = frozenset({"Polygon", "MultiPolygon"})
LENGTH_TYPES = frozenset({"LineString", "MultiLineString", "LinearRing"})
POINT_TYPES = frozenset({"Point", "MultiPoint"})

AREA_UNIT = "m²"
LENGTH_UNIT = "m"


@dataclass(frozen=True)
class MeasurementOutcome:
    """Result of measuring a single feature."""

    measurement_type: str | None
    measurement_value: float | None
    measurement_unit: str | None
    measurement_status: str
    measurement_reason: str | None
    projected_crs: str | None


def _outcome(
    kind: str | None,
    status: str,
    reason: str | None = None,
    value: float | None = None,
    unit: str | None = None,
    projected: str | None = None,
) -> MeasurementOutcome:
    return MeasurementOutcome(
        measurement_type=kind,
        measurement_value=value,
        measurement_unit=unit,
        measurement_status=status,
        measurement_reason=reason,
        projected_crs=projected,
    )


def _reproject(geom: BaseGeometry, source: CRS, target: CRS) -> BaseGeometry | None:
    if source.equals(target):
        return geom
    try:
        transformer = Transformer.from_crs(source, target, always_xy=True)
        return shapely_transform(transformer.transform, geom)
    except Exception:
        return None


def measure_geometry(geom: BaseGeometry | None, source_crs: CRS | str | None) -> MeasurementOutcome:
    """Measure one geometry according to the documented dispatch rules.

    ``source_crs`` may be a pyproj ``CRS`` (preferred) or a stored string.
    """
    if geom is None or geom.is_empty:
        return _outcome(None, MeasurementStatus.UNAVAILABLE.value, "Geometry is missing or empty.")

    geometry_type = geom.geom_type
    if geometry_type in POINT_TYPES:
        return _outcome(
            None,
            MeasurementStatus.NOT_REQUIRED.value,
            "Point geometries have no area or length to measure.",
        )
    if geometry_type in AREA_TYPES:
        kind, unit = "area", AREA_UNIT
    elif geometry_type in LENGTH_TYPES:
        kind, unit = "length", LENGTH_UNIT
    else:
        return _outcome(
            None,
            MeasurementStatus.UNSUPPORTED.value,
            f"Geometry type '{geometry_type}' is not supported for area or length measurement.",
        )

    reason: str | None = None
    work = geom
    if not geom.is_valid:
        try:
            repaired = make_valid(geom)
        except Exception:
            repaired = None
        if repaired is None or repaired.is_empty or not repaired.is_valid:
            return _outcome(
                kind,
                MeasurementStatus.UNAVAILABLE.value,
                "Geometry is invalid and could not be repaired.",
                unit=unit,
            )
        if repaired.geom_type not in (AREA_TYPES | LENGTH_TYPES):
            return _outcome(
                kind,
                MeasurementStatus.UNAVAILABLE.value,
                f"Invalid geometry could not be repaired into a measurable type "
                f"(repair produced '{repaired.geom_type}').",
                unit=unit,
            )
        work = repaired
        reason = "Geometry was invalid and was repaired with make_valid before measurement."

    crs = source_crs if isinstance(source_crs, CRS) or source_crs is None else parse_crs(source_crs)
    if crs is None:
        return _outcome(
            kind,
            MeasurementStatus.UNAVAILABLE.value,
            "Source CRS is unknown; a metric measurement cannot be computed.",
            unit=unit,
        )

    choice = choose_measurement_crs(work, crs, kind)
    if choice is None:
        return _outcome(
            kind,
            MeasurementStatus.UNAVAILABLE.value,
            "No suitable metric coordinate reference system could be determined.",
            unit=unit,
        )
    target, label = choice

    projected = _reproject(work, crs, target)
    if projected is None:
        return _outcome(
            kind,
            MeasurementStatus.UNAVAILABLE.value,
            "Reprojection to a metric coordinate reference system failed.",
            unit=unit,
        )

    raw = projected.area if kind == "area" else projected.length
    factor = metre_factor(target)
    if kind == "area":
        factor *= factor
    value = raw * factor
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return _outcome(
            kind,
            MeasurementStatus.UNAVAILABLE.value,
            "Measurement produced a non-finite value.",
            unit=unit,
        )

    return _outcome(
        kind,
        MeasurementStatus.CALCULATED.value,
        reason,
        value=value,
        unit=unit,
        projected=describe_crs(target) or label,
    )
