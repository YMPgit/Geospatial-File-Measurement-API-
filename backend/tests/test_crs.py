"""Unit tests for the CRS selection strategy."""

from __future__ import annotations

from pyproj import CRS
from shapely.geometry import box

from app.services.crs import choose_measurement_crs, describe_crs, metre_factor, parse_crs, utm_epsg


def test_utm_epsg_northern_and_southern():
    assert utm_epsg(-75.0, 42.0) == 32618
    assert utm_epsg(-75.0, -42.0) == 32718
    assert utm_epsg(0.0, 0.0) == 32631
    assert utm_epsg(179.9, 10.0) == 32660
    assert utm_epsg(-180.0, -10.0) == 32701


def test_metre_factor_known_units():
    assert metre_factor(CRS.from_epsg(32633)) == 1.0
    assert abs(metre_factor(CRS.from_epsg(2229)) - 0.30480060960121924) < 1e-15


def test_describe_crs():
    assert describe_crs(None) is None
    assert describe_crs(CRS.from_epsg(4326)) == "EPSG:4326"
    assert describe_crs(CRS.from_epsg(2229)) == "EPSG:2229"


def test_parse_crs():
    assert parse_crs(None) is None
    assert parse_crs("") is None
    assert parse_crs("not a crs at all") is None
    assert parse_crs("EPSG:4326").to_epsg() == 4326


def test_projected_source_is_measured_in_place():
    source = CRS.from_epsg(32633)
    chosen = choose_measurement_crs(box(500000, 4649776, 500100, 4649876), source, "area")

    assert chosen is not None
    crs, label = chosen
    assert crs.to_epsg() == 32633
    assert label == "EPSG:32633"


def test_geographic_geometry_uses_utm_zone():
    geom = box(2.9995, -0.0005, 3.0005, 0.0005)
    chosen = choose_measurement_crs(geom, CRS.from_epsg(4326), "area")

    assert chosen is not None
    crs, label = chosen
    assert crs.to_epsg() == 32631
    assert label == "EPSG:32631"


def test_geometry_outside_utm_domain_uses_regional_fallback():
    polar = box(10.0, 84.5, 11.0, 85.5)

    area_choice = choose_measurement_crs(polar, CRS.from_epsg(4326), "area")
    length_choice = choose_measurement_crs(polar, CRS.from_epsg(4326), "length")

    assert area_choice is not None and area_choice[1].startswith("LAEA")
    assert length_choice is not None and length_choice[1].startswith("AEQD")
    assert area_choice[0].is_projected
    assert length_choice[0].is_projected


def test_geometry_spanning_multiple_utm_zones_falls_back():
    wide = box(2.0, 0.0, 10.0, 1.0)

    chosen = choose_measurement_crs(wide, CRS.from_epsg(4326), "area")

    assert chosen is not None
    assert chosen[1].startswith("LAEA")


def test_unknown_source_returns_none():
    assert choose_measurement_crs(box(0, 0, 1, 1), None, "area") is None
