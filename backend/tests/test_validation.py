"""Phase-1 validation tests: bad requests never create a database record."""

from __future__ import annotations

import io

from app.core.config import settings
from app.utils.validators import save_upload, sanitize_filename

from tests.factories import polygon_kml, raw_zip
from tests.helpers import upload


def test_unsupported_extension_rejected(client):
    response = upload(client, "notes.txt", b"plain text")

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_missing_file_field_returns_422(client):
    response = client.post("/api/files/", data={"unrelated": "value"})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert "file" in response.json()["detail"]


def test_blank_filename_rejected(client):
    response = client.post(
        "/api/files/", files={"file": ("   ", polygon_kml(), "application/octet-stream")}
    )

    assert response.status_code == 400
    assert "filename" in response.json()["detail"].lower()


def test_oversized_upload_returns_413(client):
    oversized = b"x" * (settings.max_upload_size_bytes + 200_000)

    response = upload(client, "huge.zip", oversized, "application/zip")

    assert response.status_code == 413
    assert "size limit" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0


def test_empty_file_rejected(client):
    response = upload(client, "empty.kml", b"")

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_save_upload_enforces_limit_and_cleans_up(tmp_path):
    source = io.BytesIO(b"y" * 4096)
    destination = tmp_path / "payload.bin"

    try:
        save_upload(source, destination, max_bytes=1024)
        raised = None
    except Exception as exc:  # noqa: BLE001 - asserting the concrete type below
        raised = exc

    assert raised is not None
    assert raised.status_code == 413
    assert not destination.exists()


def test_save_upload_rejects_zero_byte_stream(tmp_path):
    destination = tmp_path / "nothing.bin"

    try:
        save_upload(io.BytesIO(b""), destination, max_bytes=1024)
        raised = None
    except Exception as exc:  # noqa: BLE001
        raised = exc

    assert raised is not None
    assert raised.status_code == 400
    assert not destination.exists()


def test_sanitize_filename_strips_directories():
    assert sanitize_filename(r"C:\Users\me\report.kml") == "report.kml"
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("  spaced.kml  ") == "spaced.kml"


def test_sanitize_filename_rejects_blank():
    try:
        sanitize_filename("   ")
    except Exception as exc:  # noqa: BLE001
        assert exc.status_code == 400
    else:
        raise AssertionError("expected sanitize_filename to reject a blank name")


def test_zip_bomb_style_expansion_rejected(client):
    # 1 MB of compressible data fits the size limit but expands past the cap.
    payload = raw_zip({"huge.shp": b"a" * (settings.max_upload_size_bytes * 21)})

    response = upload(client, "bomb.zip", payload, "application/zip")

    assert response.status_code == 400
    assert "uncompressed" in response.json()["detail"]
    assert client.get("/api/files/").json()["total"] == 0
