"""KML upload integration tests."""

from __future__ import annotations

import uuid

from tests.factories import (
    empty_kml,
    geometry_collection_kml,
    line_kml,
    not_xml_bytes,
    point_kml,
    polygon_kml,
    wrong_root_xml_bytes,
)
from tests.helpers import upload


def test_polygon_kml_upload_and_area(client):
    response = upload(client, "square.kml", polygon_kml(), "application/vnd.google-earth.kml+xml")

    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["filename"] == "square.kml"
    assert body["file_type"] == "kml"
    assert body["feature_count"] == 1
    assert body["crs"] == "EPSG:4326"
    assert body["status"] == "COMPLETED"
    assert body.get("error_message") is None

    measurements = client.get(f"/api/files/{body['id']}/measurements/").json()
    assert measurements["status"] == "COMPLETED"
    assert measurements["source_crs"] == "EPSG:4326"
    assert measurements["feature_count"] == 1

    feature = measurements["measurements"][0]
    assert feature["measurement_status"] == "CALCULATED"
    assert feature["measurement_type"] == "area"
    assert feature["measurement_unit"] == "m²"
    assert feature["projected_crs"] == "EPSG:32631"
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["Name"] == "square"
    assert feature["properties"]["description"] == "area test"
    # Geodesic reference area is ~12309 m^2; UTM distortion keeps us within 1%.
    assert abs(feature["measurement_value"] - 12309.07) < 123.09


def test_point_kml_is_not_required(client):
    response = upload(client, "point.kml", point_kml())

    assert response.status_code == 201
    file_id = response.json()["id"]
    feature = client.get(f"/api/files/{file_id}/measurements/").json()["measurements"][0]

    assert feature["measurement_status"] == "NOT_REQUIRED"
    assert feature["measurement_value"] is None
    assert feature["measurement_reason"]


def test_line_kml_length(client):
    response = upload(client, "line.kml", line_kml())

    assert response.status_code == 201
    feature = client.get(f"/api/files/{response.json()['id']}/measurements/").json()["measurements"][0]

    assert feature["measurement_status"] == "CALCULATED"
    assert feature["measurement_type"] == "length"
    assert feature["measurement_unit"] == "m"
    assert 300.0 < feature["measurement_value"] < 330.0
    assert feature["projected_crs"] == "EPSG:32631"


def test_geometry_collection_kml_is_unsupported(client):
    response = upload(client, "mixed.kml", geometry_collection_kml())

    assert response.status_code == 201
    measurements = client.get(f"/api/files/{response.json()['id']}/measurements/").json()
    assert measurements["status"] == "COMPLETED"

    feature = measurements["measurements"][0]
    assert feature["geometry_type"] == "GeometryCollection"
    assert feature["measurement_status"] == "UNSUPPORTED"
    assert "not supported" in feature["measurement_reason"]


def test_empty_kml_fails_and_persists_failed_record(client):
    response = upload(client, "empty.kml", empty_kml())

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["feature_count"] == 0
    assert body["crs"] is None
    assert body["error_message"]

    stored = client.get(f"/api/files/{body['id']}/")
    assert stored.status_code == 200
    assert stored.json()["status"] == "FAILED"

    listed = client.get("/api/files/").json()
    assert listed["total"] == 1


def test_non_xml_kml_rejected_without_record(client):
    response = upload(client, "broken.kml", not_xml_bytes())

    assert response.status_code == 400
    assert "well-formed" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_xml_with_wrong_root_rejected(client):
    response = upload(client, "shape.kml", wrong_root_xml_bytes())

    assert response.status_code == 400
    assert "<kml> root" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_uppercase_extension_accepted(client):
    response = upload(client, "SQUARE.KML", polygon_kml())

    assert response.status_code == 201
    assert response.json()["filename"] == "SQUARE.KML"
