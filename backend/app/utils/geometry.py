"""Geometry, GeoJSON and JSON-safety helpers."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry


def json_safe(obj: Any) -> Any:
    """Recursively convert numpy/pandas/datetime values into JSON-native types.

    NaN, +inf, -inf and NaT become ``None`` so payloads remain valid JSON and
    PostgreSQL ``JSONB`` accepts them.
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    try:
        if obj != obj:  # NaN / NaT / numpy nan
            return None
    except Exception:
        pass
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(key): json_safe(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(value) for value in obj]
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            return json_safe(item())
        except Exception:
            pass
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return json_safe(tolist())
        except Exception:
            pass
    isoformat = getattr(obj, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            pass
    return str(obj)


def geometry_to_geojson(geom: BaseGeometry | None) -> dict | None:
    """Convert a Shapely geometry into a JSON-serializable GeoJSON mapping."""
    if geom is None:
        return None
    return json_safe(dict(mapping(geom)))


def clean_properties(properties: dict[str, Any]) -> dict:
    """Convert a feature's attribute mapping into a JSON-safe dict."""
    return {str(key): json_safe(value) for key, value in properties.items()}


def round_value(value: float | None, digits: int = 4) -> float | None:
    """Round a measurement for presentation (the DB keeps full precision)."""
    if value is None:
        return None
    rounded = round(float(value), digits)
    return rounded if math.isfinite(rounded) else None
