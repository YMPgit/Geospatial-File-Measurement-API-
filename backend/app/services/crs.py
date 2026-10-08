"""Coordinate reference system strategy for metric measurements.

Rules (documented in the README):

* Unknown / missing source CRS -> no measurement (UNAVAILABLE); a CRS is
  never invented.
* Projected source CRS -> measured in that CRS and converted to metres using
  the axis unit conversion factor (e.g. US survey feet -> metres).
* Geographic source CRS -> reprojected to the UTM zone of the feature's
  representative point when the whole feature fits inside that zone and the
  latitude is within the UTM domain; otherwise a regional equal-area
  (LAEA, for area) or azimuthal-equidistant (AEQD, for length) projection
  centred on the feature is used as a documented fallback.
"""

from __future__ import annotations

from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

WGS84 = "EPSG:4326"

AREA_FALLBACK = "laea"
LENGTH_FALLBACK = "aeqd"


def parse_crs(value: str | None) -> CRS | None:
    """Parse a stored CRS string, returning ``None`` when it is unusable."""
    if not value:
        return None
    try:
        return CRS.from_user_input(value)
    except (CRSError, ValueError, TypeError):
        return None


def describe_crs(crs: CRS | None) -> str | None:
    """Compact, storable identifier for a CRS (EPSG/authority code when known)."""
    if crs is None:
        return None
    epsg = crs.to_epsg()
    if epsg:
        return f"EPSG:{epsg}"
    authority = crs.to_authority()
    if authority:
        return f"{authority[0]}:{authority[1]}"
    name = crs.name or ""
    if name and len(name) <= 128:
        return name
    text = crs.to_string()
    return text if len(text) <= 128 else text[:125] + "..."


def metre_factor(crs: CRS) -> float:
    """Multiply a value expressed in ``crs`` linear units by this to get metres."""
    if crs.is_geographic:
        return 1.0
    try:
        factor = crs.axis_info[0].unit_conversion_factor
    except (IndexError, AttributeError, CRSError):
        return 1.0
    return float(factor) if factor else 1.0


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the UTM zone containing ``(lon, lat)``."""
    zone = int((lon + 180.0) // 6.0) + 1
    zone = min(max(zone, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


def _to_wgs84(geom: BaseGeometry, source: CRS) -> BaseGeometry | None:
    """Return ``geom`` expressed in EPSG:4326 (or ``None`` on failure)."""
    target = CRS.from_epsg(4326)
    if source.equals(target):
        return geom
    try:
        transformer = Transformer.from_crs(source, target, always_xy=True)
        return shapely_transform(transformer.transform, geom)
    except Exception:
        return None


def _regional_fallback_crs(lon: float, lat: float, kind: str) -> tuple[CRS, str]:
    proj = AREA_FALLBACK if kind == "area" else LENGTH_FALLBACK
    crs = CRS.from_proj4(
        f"+proj={proj} +lat_0={lat:.6f} +lon_0={lon:.6f} +x_0=0 +y_0=0 "
        "+datum=WGS84 +units=m +no_defs"
    )
    label = f"{proj.upper()} lon_0={lon:.4f} lat_0={lat:.4f}"
    return crs, label


def choose_measurement_crs(
    geom: BaseGeometry, source: CRS | None, kind: str
) -> tuple[CRS, str] | None:
    """Pick the CRS the measurement should be computed in.

    Returns ``(crs, label)`` or ``None`` when no usable CRS exists.
    """
    if source is None:
        return None

    if source.is_projected:
        return source, describe_crs(source) or "projected"

    if not source.is_geographic:
        return None

    geographic = _to_wgs84(geom, source)
    if geographic is None or geographic.is_empty:
        return None

    point = geographic.representative_point()
    lon, lat = point.x, point.y
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None

    if -80.0 <= lat <= 84.0:
        epsg = utm_epsg(lon, lat)
        utm = CRS.from_epsg(epsg)
        zone_left = (epsg % 100 - 1) * 6 - 180.0
        minx, _, maxx, _ = geographic.bounds
        if minx >= zone_left and maxx <= zone_left + 6.0:
            return utm, f"EPSG:{epsg}"

    return _regional_fallback_crs(lon, lat, kind)
