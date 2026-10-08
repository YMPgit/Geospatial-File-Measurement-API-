"""Unit tests for the per-feature measurement dispatch rules."""

from __future__ import annotations

import math

from shapely.geometry import GeometryCollection, LineString, Point, Polygon, box

from app.services.measurement import measure_geometry


def test_missing_geometry_is_unavailable():
    outcome = measure_geometry(None, "EPSG:4326")

    assert outcome.measurement_status == "UNAVAILABLE"
    assert outcome.measurement_value is None
    assert "missing or empty" in outcome.measurement_reason


def test_empty_geometry_is_unavailable():
    outcome = measure_geometry(Polygon(), "EPSG:4326")

    assert outcome.measurement_status == "UNAVAILABLE"


def test_point_is_not_required():
    outcome = measure_geometry(Point(3.0, 0.0), "EPSG:4326")

    assert outcome.measurement_status == "NOT_REQUIRED"
    assert outcome.measurement_value is None
    assert outcome.measurement_type is None


def test_geometry_collection_is_unsupported():
    geom = GeometryCollection([Point(0, 0), LineString([(0, 0), (1, 0)])])
    outcome = measure_geometry(geom, "EPSG:4326")

    assert outcome.measurement_status == "UNSUPPORTED"
    assert "not supported" in outcome.measurement_reason


def test_unknown_crs_is_unavailable_with_type_preserved():
    outcome = measure_geometry(box(0, 0, 1, 1), None)

    assert outcome.measurement_status == "UNAVAILABLE"
    assert outcome.measurement_type == "area"
    assert outcome.measurement_unit == "m²"
    assert "CRS" in outcome.measurement_reason


def test_unparseable_crs_string_is_unavailable():
    outcome = measure_geometry(box(0, 0, 1, 1), "definitely-not-a-crs")

    assert outcome.measurement_status == "UNAVAILABLE"


def test_geographic_polygon_yields_utm_area():
    geom = box(2.9995, -0.0005, 3.0005, 0.0005)
    outcome = measure_geometry(geom, "EPSG:4326")

    assert outcome.measurement_status == "CALCULATED"
    assert outcome.measurement_type == "area"
    assert outcome.measurement_unit == "m²"
    assert outcome.projected_crs == "EPSG:32631"
    assert abs(outcome.measurement_value - 12309.07) < 123.09


def test_projected_line_length_is_exact():
    geom = LineString([(500000, 4649776), (500300, 4649776)])
    outcome = measure_geometry(geom, "EPSG:32633")

    assert outcome.measurement_status == "CALCULATED"
    assert outcome.measurement_type == "length"
    assert outcome.measurement_unit == "m"
    assert math.isclose(outcome.measurement_value, 300.0, rel_tol=1e-12)
    assert outcome.projected_crs == "EPSG:32633"
    assert outcome.measurement_reason is None


def test_invalid_polygon_is_repaired():
    bowtie = Polygon([(0, 0), (100, 100), (100, 0), (0, 100), (0, 0)])
    assert not bowtie.is_valid

    outcome = measure_geometry(bowtie, "EPSG:32633")

    assert outcome.measurement_status == "CALCULATED"
    assert "repaired" in outcome.measurement_reason
    assert math.isclose(outcome.measurement_value, 5000.0, rel_tol=1e-9)


def test_feet_crs_converts_area_to_square_metres():
    geom = box(1000000, 200000, 1000100, 200100)
    outcome = measure_geometry(geom, "EPSG:2229")

    assert outcome.measurement_status == "CALCULATED"
    assert outcome.projected_crs == "EPSG:2229"
    assert abs(outcome.measurement_value - 929.0341162) < 1e-6
