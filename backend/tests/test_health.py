"""Health check tests."""

from __future__ import annotations


def test_health_returns_healthy(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_reports_api_metadata(client):
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["health"] == "/health"
    assert payload["docs"] == "/docs"
