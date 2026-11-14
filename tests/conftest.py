from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/counselling_test")

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def migrate_test_schema() -> None:
	config = Config("backend/alembic.ini")
	command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def fake_embedder():
	"""Unit tests never load or download the real embedding model."""
	from backend.app import embeddings

	def _forbidden(*args, **kwargs):
		raise RuntimeError("Real embedding model must not load in tests")

	original = embeddings.FastEmbedEmbedder
	embeddings.FastEmbedEmbedder = _forbidden
	embeddings.set_embedder(embeddings.FakeEmbedder())
	yield
	embeddings.FastEmbedEmbedder = original
	embeddings.set_embedder(None)
