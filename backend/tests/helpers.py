"""Thin HTTP helpers shared by the API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def upload(
    client: TestClient,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
):
    return client.post("/api/files/", files={"file": (filename, content, content_type)})
