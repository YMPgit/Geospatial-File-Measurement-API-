"""Test fixtures.

Environment variables are assigned **before** any ``app`` import so settings
and the SQLAlchemy engine point at a throwaway SQLite database.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="geoapi_tests_"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("MAX_UPLOAD_SIZE_MB", "1")
os.environ.setdefault("UPLOAD_DIR", str(_TEST_ROOT / "uploads"))
if "TEST_DATABASE_URL" in os.environ:
    # Run the suite against a real database, e.g.:
    #   TEST_DATABASE_URL=postgresql+psycopg2://postgres:pass@localhost:5432/geo_test pytest
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(_TEST_ROOT / "test.db"))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def clean_state():
    """Give every test an empty database and an empty upload directory."""
    from app.core.config import settings
    from app.db.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    if settings.upload_path.exists():
        shutil.rmtree(settings.upload_path, ignore_errors=True)
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
