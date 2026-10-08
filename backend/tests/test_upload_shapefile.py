"""Shapefile ZIP upload integration tests."""

from __future__ import annotations

from tests.factories import (
    bowtie_gdf,
    corrupt_shapefile_zip,
    feet_gdf,
    line_gdf,
    missing_component_zip,
    multi_shapefile_zip,
    raw_zip,
    shapefile_zip,
    square_gdf,
    symlink_zip,
    traversal_zip,
)
from tests.helpers import upload


def test_square_shapefile_exact_area(client):
    response = upload(client, "square.zip", shapefile_zip(square_gdf()), "application/zip")

    assert response.status_code == 201
    body = response.json()
    assert body["file_type"] == "shapefile"
    assert body["feature_count"] == 1
    assert body["crs"] == "EPSG:32633"
    assert body["status"] == "COMPLETED"

    feature = client.get(f"/api/files/{body['id']}/measurements/").json()["measurements"][0]
    assert feature["measurement_status"] == "CALCULATED"
    assert feature["measurement_type"] == "area"
    assert feature["measurement_unit"] == "m²"
    assert feature["projected_crs"] == "EPSG:32633"
    assert abs(feature["measurement_value"] - 10000.0) < 0.01
    assert feature["properties"] == {"name": "square"}


def test_shapefile_without_prj_is_unavailable_not_failed(client):
    response = upload(
        client, "no_prj.zip", shapefile_zip(square_gdf(), include_prj=False), "application/zip"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["crs"] is None

    feature = client.get(f"/api/files/{body['id']}/measurements/").json()["measurements"][0]
    assert feature["measurement_status"] == "UNAVAILABLE"
    assert feature["measurement_value"] is None
    assert "CRS" in feature["measurement_reason"]


def test_line_shapefile_exact_length(client):
    response = upload(client, "line.zip", shapefile_zip(line_gdf()), "application/zip")

    assert response.status_code == 201
    feature = client.get(f"/api/files/{response.json()['id']}/measurements/").json()["measurements"][0]

    assert feature["measurement_status"] == "CALCULATED"
    assert feature["measurement_type"] == "length"
    assert feature["measurement_unit"] == "m"
    assert abs(feature["measurement_value"] - 300.0) < 1e-6


def test_us_survey_feet_converted_to_metres(client):
    response = upload(client, "feet.zip", shapefile_zip(feet_gdf()), "application/zip")

    assert response.status_code == 201
    body = response.json()
    assert body["crs"] == "EPSG:2229"

    feature = client.get(f"/api/files/{body['id']}/measurements/").json()["measurements"][0]
    # 100 ft x 100 ft = 10000 sq US survey feet = 929.0341 m^2
    assert feature["measurement_status"] == "CALCULATED"
    assert abs(feature["measurement_value"] - 929.0341) < 0.001
    assert feature["measurement_unit"] == "m²"


def test_multiple_shapefiles_uses_lexicographic_first(client):
    response = upload(client, "multi.zip", multi_shapefile_zip(), "application/zip")

    assert response.status_code == 201
    body = response.json()
    assert body["feature_count"] == 1

    feature = client.get(f"/api/files/{body['id']}/measurements/").json()["measurements"][0]
    assert abs(feature["measurement_value"] - 10000.0) < 0.01  # aaa.shp (not the 200 m one)


def test_invalid_polygon_is_repaired_before_measurement(client):
    response = upload(client, "bowtie.zip", shapefile_zip(bowtie_gdf()), "application/zip")

    assert response.status_code == 201
    feature = client.get(f"/api/files/{response.json()['id']}/measurements/").json()["measurements"][0]

    assert feature["measurement_status"] == "CALCULATED"
    assert feature["measurement_value"] > 0
    assert "repaired" in feature["measurement_reason"]


def test_missing_required_component_rejected_without_record(client):
    response = upload(client, "partial.zip", missing_component_zip(), "application/zip")

    assert response.status_code == 400
    assert "missing required Shapefile component" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_zip_without_shapefile_rejected(client):
    response = upload(client, "docs.zip", raw_zip({"readme.txt": b"hello"}), "application/zip")

    assert response.status_code == 400
    assert "does not contain a .shp" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_path_traversal_zip_rejected(client):
    response = upload(client, "evil.zip", traversal_zip(), "application/zip")

    assert response.status_code == 400
    assert "escapes the archive root" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_symlink_zip_rejected(client):
    response = upload(client, "links.zip", symlink_zip(), "application/zip")

    assert response.status_code == 400
    assert "symbolic link" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_non_zip_bytes_rejected(client):
    response = upload(client, "fake.zip", b"PK not really a zip archive", "application/zip")

    assert response.status_code == 400
    assert "not a valid ZIP" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_corrupt_shapefile_marks_record_failed(client):
    response = upload(client, "corrupt.zip", corrupt_shapefile_zip(), "application/zip")

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["file_type"] == "shapefile"
    assert body["error_message"]
    assert body["feature_count"] == 0
    assert "shp_extract" not in body["error_message"]
    assert "Temp" not in body["error_message"]
    assert "broken.shp" in body["error_message"]

    assert client.get("/api/files/").json()["total"] == 1
    stored = client.get(f"/api/files/{body['id']}/").json()
    assert stored["status"] == "FAILED"
    assert stored["error_message"]

    measurements = client.get(f"/api/files/{body['id']}/measurements/").json()
    assert measurements["status"] == "FAILED"
    assert measurements["measurements"] == []
