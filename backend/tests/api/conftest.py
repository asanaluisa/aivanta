"""API integration tests against a real PostgreSQL database.

Skipped automatically unless the web stack is installed *and*
``AIVANTA_TEST_DATABASE_URL`` points to a disposable database, e.g.::

    AIVANTA_TEST_DATABASE_URL=postgresql+psycopg://aivanta:aivanta@localhost:5432/aivanta_test pytest
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

URL = os.environ.get("AIVANTA_TEST_DATABASE_URL")
if not URL:
    pytest.skip("AIVANTA_TEST_DATABASE_URL not set", allow_module_level=True)

os.environ["AIVANTA_DATABASE_URL"] = URL
os.environ.setdefault("AIVANTA_JWT_SECRET", "api-test-secret-that-is-at-least-32-bytes")
os.environ.setdefault("AIVANTA_DEMO_PASSWORD", "test-password")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from aivanta_core import synthetic  # noqa: E402

SQL = Path(__file__).resolve().parents[2] / "migrations" / "sql" / "0001_initial.sql"
PASSWORD = os.environ["AIVANTA_DEMO_PASSWORD"]


def _reset_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.exec_driver_sql(SQL.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def engine():
    from app.config import get_settings

    get_settings.cache_clear()
    eng = create_engine(URL, future=True)
    _reset_schema(eng)
    return eng


@pytest.fixture(scope="session")
def seeded(engine):
    import json

    from app.db import session_factory
    from app.repository import clear_cache
    from app.seed import ATTRIBUTION_SAMPLE, DEMO_ACCOUNTS, seed_organization

    with session_factory()() as db:
        seed_organization(db, synthetic.generate(days=30), key="org_demo", name="Demo (synthetic)",
                          accounts=DEMO_ACCOUNTS, password=PASSWORD,
                          attribution=json.loads(ATTRIBUTION_SAMPLE.read_text()))
        seed_organization(db, synthetic.generate(seed=7, days=20), key="org_northwind",
                          name="Northwind (synthetic)",
                          accounts=[("admin@northwind.demo", "admin", "NW Admin")], password=PASSWORD)
        db.commit()
    clear_cache()
    return True


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import create_app

    return TestClient(create_app())


def login(client, email: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return login(client, "admin@aivanta.demo")


@pytest.fixture(scope="session")
def viewer(client):
    return login(client, "viewer@aivanta.demo")


@pytest.fixture(scope="session")
def finance(client):
    return login(client, "finance@aivanta.demo")


@pytest.fixture(scope="session")
def analyst(client):
    return login(client, "analyst@aivanta.demo")
