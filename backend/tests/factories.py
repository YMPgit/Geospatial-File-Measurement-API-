"""Builders for the sample KML/Shapefile fixtures used across the test suite."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point, box

KML_NS = 'xmlns="http://www.opengis.net/kml/2.2"'


def kml_document(placemarks: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<kml {KML_NS}><Document>{placemarks}</Document></kml>"
    ).encode("utf-8")


def _polygon_coordinates(lon_min: float, lon_max: float, lat_min: float, lat_max: float) -> str:
    return (
        f"{lon_min},{lat_min},0 {lon_max},{lat_min},0 {lon_max},{lat_max},0 "
        f"{lon_min},{lat_max},0 {lon_min},{lat_min},0"
    )


def polygon_kml() -> bytes:
    """A ~111 m square near 3°E / equator (inside UTM zone 31)."""
    return kml_document(
        '<Placemark id="p1"><name>square</name><description>area test</description>'
        "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
        + _polygon_coordinates(2.9995, 3.0005, -0.0005, 0.0005)
        + "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>"
    )


def point_kml() -> bytes:
    return kml_document(
        '<Placemark id="p1"><name>point</name><Point><coordinates>3.0,0.0,0</coordinates>'
        "</Point></Placemark>"
    )


def line_kml() -> bytes:
    return kml_document(
        '<Placemark id="p1"><name>line</name><LineString>'
        "<coordinates>2.999,0.001,0 3.001,0.003,0</coordinates>"
        "</LineString></Placemark>"
    )


def geometry_collection_kml() -> bytes:
    """A mixed MultiGeometry, which GDAL reads as a GeometryCollection."""
    return kml_document(
        '<Placemark id="p1"><name>mixed</name><MultiGeometry>'
        "<Point><coordinates>3.0,0.0,0</coordinates></Point>"
        "<LineString><coordinates>2.999,-0.001,0 3.001,0.001,0</coordinates></LineString>"
        "</MultiGeometry></Placemark>"
    )


def empty_kml() -> bytes:
    return kml_document("<name>nothing here</name>")


def not_xml_bytes() -> bytes:
    return b"this is definitely not xml at all"


def wrong_root_xml_bytes() -> bytes:
    return b'<?xml version="1.0"?><shape><feature/></shape>'


def square_gdf(size: float = 100.0, crs: str = "EPSG:32633") -> gpd.GeoDataFrame:
    """A metric square of ``size`` x ``size`` metres in UTM 33N."""
    minx, miny = 500000.0, 4649776.0
    return gpd.GeoDataFrame(
        {"name": ["square"]},
        geometry=[box(minx, miny, minx + size, miny + size)],
        crs=crs,
    )


def feet_gdf() -> gpd.GeoDataFrame:
    """A 100 ft x 100 ft square in EPSG:2229 (US survey feet)."""
    return gpd.GeoDataFrame(
        {"name": ["feet"]},
        geometry=[box(1000000.0, 200000.0, 1000100.0, 200100.0)],
        crs="EPSG:2229",
    )


def line_gdf(length: float = 300.0) -> gpd.GeoDataFrame:
    minx, miny = 500000.0, 4649776.0
    return gpd.GeoDataFrame(
        {"name": ["line"]},
        geometry=[LineString([(minx, miny), (minx + length, miny)])],
        crs="EPSG:32633",
    )


def point_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": ["pt"]},
        geometry=[Point(500000.0, 4649776.0)],
        crs="EPSG:32633",
    )


def bowtie_gdf() -> gpd.GeoDataFrame:
    """An invalid self-intersecting polygon (area 0 until repaired)."""
    from shapely.geometry import Polygon

    bowtie = Polygon([(0, 0), (100, 100), (100, 0), (0, 100), (0, 0)])
    return gpd.GeoDataFrame({"name": ["bowtie"]}, geometry=[bowtie], crs="EPSG:32633")


def shapefile_zip(gdf: gpd.GeoDataFrame, *, include_prj: bool = True, name: str = "layer") -> bytes:
    """Zip a GeoDataFrame written as a Shapefile (as GDAL writes it)."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / name
        base.mkdir()
        gdf.to_file(base / f"{name}.shp", engine="pyogrio")
        if not include_prj:
            (base / f"{name}.prj").unlink(missing_ok=True)
        return _zip_dir(base)


def multi_shapefile_zip() -> bytes:
    """Two shapefiles in one ZIP; the lexicographically first must be used."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "aaa").mkdir()
        (base / "bbb").mkdir()
        square_gdf().to_file(base / "aaa" / "aaa.shp", engine="pyogrio")
        square_gdf(size=200.0).to_file(base / "bbb" / "bbb.shp", engine="pyogrio")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder in ("aaa", "bbb"):
                for path in (base / folder).iterdir():
                    zf.write(path, f"{folder}/{path.name}")
        return buffer.getvalue()


def raw_zip(members: dict[str, bytes]) -> bytes:
    """Build a ZIP from raw member bytes (for structurally-invalid archives)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for member_name, payload in members.items():
            zf.writestr(member_name, payload)
    return buffer.getvalue()


def corrupt_shapefile_zip() -> bytes:
    return raw_zip(
        {
            "broken.shp": b"not a shapefile" * 8,
            "broken.shx": b"not an index" * 8,
            "broken.dbf": b"not a dbf" * 8,
        }
    )


def missing_component_zip() -> bytes:
    return raw_zip({"part.shp": b"x" * 64, "part.shx": b"y" * 64})


def traversal_zip() -> bytes:
    return raw_zip(
        {
            "../evil.shp": b"x" * 64,
            "../evil.shx": b"y" * 64,
            "../evil.dbf": b"z" * 64,
        }
    )


def symlink_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        info = zipfile.ZipInfo("link.shp")
        info.external_attr = (0o120777 << 16) | 0o2000000
        zf.writestr(info, "/etc/passwd")
        zf.writestr("link.shx", b"y" * 16)
        zf.writestr("link.dbf", b"z" * 16)
    return buffer.getvalue()


def _zip_dir(directory: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.iterdir()):
            zf.write(path, path.name)
    return buffer.getvalue()
