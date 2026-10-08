"""Tests for the read/list endpoints, response formatting and error handling."""

from __future__ import annotations

import uuid

from app.core.config import settings
from app.main import app

from tests.factories import feet_gdf, polygon_kml, shapefile_zip
from tests.helpers import upload


def test_unknown_file_id_returns_404(client):
    response = client.get(f"/api/files/{uuid.uuid4()}/")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found."}


def test_unknown_file_measurements_returns_404(client):
    response = client.get(f"/api/files/{uuid.uuid4()}/measurements/")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found."}


def test_malformed_uuid_returns_422(client):
    response = client.get("/api/files/not-a-uuid/")

    assert response.status_code == 422


def test_delete_file_removes_record_measurements_and_stored_file(client):
    uploaded = upload(client, "square.kml", polygon_kml()).json()
    upload(client, "feet.zip", shapefile_zip(feet_gdf()), "application/zip")
    total_before = client.get("/api/files/").json()["total"]
    stored_before = {path.name for path in settings.upload_path.iterdir()}
    assert len(stored_before) == 2

    response = client.delete(f"/api/files/{uploaded['id']}/")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/files/").json()["total"] == total_before - 1
    assert client.get(f"/api/files/{uploaded['id']}/").status_code == 404
    assert client.get(f"/api/files/{uploaded['id']}/measurements/").status_code == 404
    remaining = [path.name for path in settings.upload_path.iterdir()]
    assert len(remaining) == 1
    assert remaining[0] in stored_before


def test_delete_unknown_file_returns_404(client):
    response = client.delete(f"/api/files/{uuid.uuid4()}/")

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found."}


def test_get_file_metadata(client):
    uploaded = upload(client, "square.kml", polygon_kml()).json()

    response = client.get(f"/api/files/{uploaded['id']}/")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == uploaded["id"]
    assert body["filename"] == "square.kml"
    assert body["file_type"] == "kml"
    assert body["feature_count"] == 1
    assert body["source_crs"] == "EPSG:4326"
    assert body["status"] == "COMPLETED"
    assert body["error_message"] is None
    assert body["created_at"]
    assert body["updated_at"]


def test_upload_success_body_has_exact_keys(client):
    response = upload(client, "square.kml", polygon_kml())

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "filename", "file_type", "feature_count", "crs", "status"}
    assert body["status"] == "COMPLETED"
    assert body["crs"] == "EPSG:4326"


def test_list_files_newest_first_with_paging(client):
    first = upload(client, "one.kml", polygon_kml()).json()
    second = upload(client, "two.kml", polygon_kml()).json()

    response = client.get("/api/files/")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0
    listed_ids = [item["id"] for item in body["items"]]
    assert set(listed_ids) == {first["id"], second["id"]}
    assert listed_ids[0] == second["id"]  # newest first

    page = client.get("/api/files/?limit=1&offset=1").json()
    assert page["total"] == 2
    assert len(page["items"]) == 1


def test_list_files_empty(client):
    body = client.get("/api/files/").json()

    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_list_rejects_invalid_paging(client):
    assert client.get("/api/files/?limit=0").status_code == 422
    assert client.get("/api/files/?limit=101").status_code == 422
    assert client.get("/api/files/?offset=-1").status_code == 422


def test_measurements_payload_is_json_safe(client):
    uploaded = upload(client, "square.kml", polygon_kml()).json()

    response = client.get(f"/api/files/{uploaded['id']}/measurements/")

    text = response.text
    assert "NaN" not in text
    assert "NaT" not in text

    feature = response.json()["measurements"][0]
    assert feature["properties"]["timestamp"] is None  # KML has no timestamps
    assert feature["properties"]["drawOrder"] is None


def test_measurement_values_are_rounded_to_4_decimals(client):
    uploaded = upload(client, "feet.zip", shapefile_zip(feet_gdf()), "application/zip").json()

    feature = client.get(f"/api/files/{uploaded['id']}/measurements/").json()["measurements"][0]

    assert feature["measurement_value"] == 929.0341
    assert feature["measurement_value"] == round(feature["measurement_value"], 4)


def test_unhandled_error_returns_sanitized_500(client, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("app.api.files.process_upload", explode)

    response = upload(client, "square.kml", polygon_kml())

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text


def test_measurements_include_geojson_geometry(client):
    uploaded = upload(client, "square.kml", polygon_kml()).json()

    feature = client.get(f"/api/files/{uploaded['id']}/measurements/").json()["measurements"][0]

    assert feature["geometry"]["type"] == "Polygon"
    assert len(feature["geometry"]["coordinates"][0]) == 5


def test_docs_endpoint_available(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/files/" in paths
    assert "/api/files/{file_id}/measurements/" in paths
    assert app.title
