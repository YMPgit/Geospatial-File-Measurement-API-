"""Unit tests for JSON-safe conversion helpers."""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd

from app.utils.geometry import clean_properties, geometry_to_geojson, json_safe, round_value
from shapely.geometry import Point


def test_nan_and_infinity_become_null():
    assert json_safe(float("nan")) is None
    assert json_safe(float("inf")) is None
    assert json_safe(float("-inf")) is None
    assert json_safe(np.float64("nan")) is None


def test_nat_becomes_null():
    assert json_safe(pd.NaT) is None


def test_numpy_scalars_become_native_python():
    assert json_safe(np.int64(5)) == 5
    assert type(json_safe(np.int64(5))) is int
    assert json_safe(np.float32(1.5)) == 1.5
    assert json_safe(np.bool_(True)) is True


def test_datetime_becomes_isoformat():
    assert json_safe(datetime(2024, 5, 1, 12, 30)) == "2024-05-01T12:30:00"


def test_nested_structures_are_recursed():
    payload = {"a": np.nan, "b": [np.int64(1), np.float64("nan")], "c": {"d": pd.NaT}}

    assert json_safe(payload) == {"a": None, "b": [1, None], "c": {"d": None}}


def test_clean_properties_keeps_values_and_stringifies_keys():
    props = clean_properties({"name": "road", "lanes": np.int64(2), "temp": np.nan})

    assert props == {"name": "road", "lanes": 2, "temp": None}


def test_geometry_to_geojson_returns_lists():
    geojson = geometry_to_geojson(Point(1.5, 2.5))

    assert geojson["type"] == "Point"
    assert geojson["coordinates"] == [1.5, 2.5]
    assert all(isinstance(coord, float) for coord in geojson["coordinates"])


def test_geometry_to_geojson_handles_none():
    assert geometry_to_geojson(None) is None


def test_round_value():
    assert round_value(1.23456789) == 1.2346
    assert round_value(None) is None
    assert round_value(float("nan")) is None
    assert math.isclose(round_value(929.0341162), 929.0341)
