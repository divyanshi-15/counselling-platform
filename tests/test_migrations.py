from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from backend.app import models  # noqa: F401
from backend.app.db import Base, engine


def test_migrated_schema_matches_models_metadata() -> None:
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        differences = compare_metadata(migration_context, Base.metadata)

    assert differences == [], f"Database schema differs from models metadata: {differences}"
