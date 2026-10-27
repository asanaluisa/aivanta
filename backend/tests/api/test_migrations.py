"""The hand-written migration SQL and the ORM models must describe the same schema."""
import pytest

alembic = pytest.importorskip("alembic")

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402


def test_models_match_migration(engine):
    from app import models  # noqa: F401
    from app.db import Base

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], diff
