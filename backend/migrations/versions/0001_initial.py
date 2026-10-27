"""Initial schema.

The DDL lives in ``migrations/sql/0001_initial.sql`` so it can be reviewed and
applied with plain ``psql`` as well; ``tests/api/test_migrations.py`` checks
it matches the ORM models exactly.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-27
"""
from pathlib import Path

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql" / "0001_initial.sql"

TABLES = [
    "audit_events", "roi_snapshots", "assumption_sets", "alerts", "budgets", "benefit_claims",
    "cost_items", "usage_events", "tasks", "attribution_rules", "ingestion_batches", "baselines",
    "experiments", "use_cases", "model_prices", "ai_models", "ai_providers", "users", "departments",
    "organizations",
]


def upgrade() -> None:
    # exec_driver_sql: no bind-parameter parsing, and psycopg runs the whole
    # multi-statement script in one round trip.
    op.get_bind().exec_driver_sql(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
