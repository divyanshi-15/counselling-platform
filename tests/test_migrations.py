from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from backend.app import models  # noqa: F401
from backend.app.db import Base, engine


def test_migrated_schema_matches_models_metadata() -> None:
    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        differences = compare_metadata(migration_context, Base.metadata)

    assert differences == [], f"Database schema differs from models metadata: {differences}"


def test_therapist_booking_migration_has_unique_constraints_and_foreign_keys() -> None:
    with engine.connect() as connection:
        inspector = inspect(connection)
        availability_unique = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("availability_slots")
        }
        booking_unique = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("bookings")
        }
        availability_fks = inspector.get_foreign_keys("availability_slots")
        booking_fks = inspector.get_foreign_keys("bookings")
        therapist_fks = inspector.get_foreign_keys("therapist_profiles")
        form_fks = inspector.get_foreign_keys("intake_forms")
        response_fks = inspector.get_foreign_keys("intake_responses")

    assert ("therapist_id", "starts_at", "ends_at") in availability_unique
    assert ("availability_slot_id",) in booking_unique
    assert any(fk["constrained_columns"] == ["user_id"] and fk["referred_table"] == "users"
               for fk in therapist_fks)
    assert any(fk["constrained_columns"] == ["practice_id"] and fk["referred_table"] == "practices"
               for fk in therapist_fks)
    assert any(fk["constrained_columns"] == ["therapist_id"] and fk["referred_table"] == "therapist_profiles"
               for fk in availability_fks)
    assert any(fk["constrained_columns"] == ["client_id"] and fk["referred_table"] == "users"
               for fk in booking_fks)
    assert any(fk["constrained_columns"] == ["availability_slot_id"] and fk["referred_table"] == "availability_slots"
               for fk in booking_fks)
    assert any(fk["constrained_columns"] == ["therapist_id"] and fk["referred_table"] == "therapist_profiles"
               for fk in form_fks)
    assert any(fk["constrained_columns"] == ["booking_id"] and fk["referred_table"] == "bookings"
               for fk in response_fks)
    assert any(fk["constrained_columns"] == ["client_id"] and fk["referred_table"] == "users"
               for fk in response_fks)
