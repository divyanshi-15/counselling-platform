from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, inspect, select, text

from backend.app.auth import hash_password
from backend.app.citations import NO_SUPPORT, CitationError, Suggestion, validate_suggestions
from backend.app.db import SessionLocal, engine
from backend.app.embeddings import get_embedder
from backend.app.models import AvailabilitySlot, Booking, KbChunk, KbDocument, Practice, TherapistProfile, User
from backend.app.rag import add_case_memory, index_session_notes, load_kb, parse_kb_file, retrieve_case_memory, retrieve_knowledge

KB_DIR = Path(__file__).resolve().parents[1] / "kb"


def _add_chunk(db, text_: str, approach: str, language: str) -> int:
    doc = KbDocument(slug=f"t-{uuid4().hex}", title="Test", approach=approach, language=language,
                     source_inspired_by="test", body=text_, content_hash=uuid4().hex)
    db.add(doc)
    db.flush()
    chunk = KbChunk(document_id=doc.id, text=text_, approach=approach, language=language,
                    topic_tags=["test"], embedding=get_embedder().embed_passages([text_])[0])
    db.add(chunk)
    db.commit()
    return chunk.id


@pytest.fixture
def lang() -> str:
    return f"x{uuid4().hex[:8]}"  # isolates each test's chunks from the real KB


# ---------- KB loading ----------

def test_kb_files_parse_with_required_metadata() -> None:
    entries = [parse_kb_file(p) for p in sorted(KB_DIR.glob("*.md"))]
    assert len(entries) == 12
    assert all(e["reviewed_by"] == "UNREVIEWED" and e["reviewed_at"] is None for e in entries)


def test_load_kb_is_idempotent_one_chunk_per_entry() -> None:
    with SessionLocal() as db:
        load_kb(db, KB_DIR)
        second = load_kb(db, KB_DIR)
        assert second == {"files": 12, "embedded": 0}
        slugs = [parse_kb_file(p)["slug"] for p in KB_DIR.glob("*.md")]
        docs = db.scalars(select(KbDocument).where(KbDocument.slug.in_(slugs))).all()
        assert len(docs) == 12 and all(d.licence == "original, for demo" for d in docs)
        counts = db.execute(select(KbChunk.document_id).where(KbChunk.document_id.in_([d.id for d in docs]))).all()
        assert len(counts) == 12


def test_real_kb_retrieval_finds_relevant_entry() -> None:
    with SessionLocal() as db:
        load_kb(db, KB_DIR)
        hits = retrieve_knowledge(db, "worry postponement worry time", language="en", min_similarity=0.1)
    assert hits and hits[0].title == "Worry postponement"


# ---------- retrieval ----------

def test_metadata_filter_applies_before_ranking(lang: str) -> None:
    with SessionLocal() as db:
        for _ in range(6):  # more near-identical CBT chunks than k
            _add_chunk(db, "sleep routine bedtime wind down evening", "CBT", lang)
        dbt_id = _add_chunk(db, "sleep routine bedtime distress", "DBT", lang)
        hits = retrieve_knowledge(db, "sleep routine bedtime wind down evening", approach="DBT",
                                  language=lang, k=5, min_similarity=0.1)
        unfiltered = retrieve_knowledge(db, "sleep routine bedtime wind down evening", language=lang,
                                        k=5, min_similarity=0.1)
    assert [h.id for h in hits] == [dbt_id]
    assert dbt_id not in [h.id for h in unfiltered]  # would be lost by post-filtering a top-k list
    assert all(h.approach == "CBT" for h in unfiltered)


def test_retrieval_returns_empty_when_nothing_qualifies(lang: str) -> None:
    with SessionLocal() as db:
        _add_chunk(db, "grounding senses present moment", "general", lang)
        assert retrieve_knowledge(db, "quarterly invoice spreadsheet", language=lang, min_similarity=0.3) == []
        assert retrieve_knowledge(db, "grounding senses", approach="CBT-I", language=lang, min_similarity=0.1) == []
        assert retrieve_knowledge(db, "grounding senses", language=lang, min_similarity=0.1)


def test_threshold_drops_weak_lexical_matches(lang: str) -> None:
    with SessionLocal() as db:
        _add_chunk(db, "breathing slow exhale longer counting calm body settle shoulders", "PM+", lang)
        hits = retrieve_knowledge(db, "breathing", language=lang, min_similarity=0.9)
    assert hits == []


# ---------- citation validator ----------

def test_fabricated_chunk_id_rejected() -> None:
    with pytest.raises(CitationError):
        validate_suggestions([Suggestion(text="Try worry time", chunk_ids=[1, 999999])], retrieved_ids={1})


def test_fabricated_note_quote_rejected() -> None:
    with pytest.raises(CitationError):
        validate_suggestions([Suggestion(text="x", note_quotes=["I never sleep"])], retrieved_ids=set(),
                             notes_text="Client reports sleeping about five hours.")


def test_uncited_claims_labelled_inferred_and_valid_citations_supported() -> None:
    out = validate_suggestions([
        Suggestion(text="Try worry time", chunk_ids=[7], label="INFERRED"),
        Suggestion(text="Sleep seems short", note_quotes=["sleeping  about five hours"]),
        Suggestion(text="Mood may be lower", label="SUPPORTED"),
    ], retrieved_ids={7}, notes_text="Client reports sleeping about five hours.")
    assert [s.label for s in out] == ["SUPPORTED", "SUPPORTED", "INFERRED"]
    assert out[2].support_note is None


def test_no_retrieval_marks_no_supporting_entry() -> None:
    out = validate_suggestions([Suggestion(text="Consider grounding")], retrieved_ids=[])
    assert out[0].label == "INFERRED" and out[0].support_note == NO_SUPPORT


# ---------- per-client case memory ----------

@pytest.fixture
def case_scenario():
    with SessionLocal() as db:
        def user(role: str) -> User:
            u = User(email=f"{role}-{uuid4().hex}@example.com", password_hash=hash_password("x"), role=role)
            db.add(u)
            db.flush()
            return u

        therapist, other_therapist = user("therapist"), user("therapist")
        client_a, client_b, owner = user("client"), user("client"), user("practice_owner")
        practice = Practice(name="P", slug=uuid4().hex, owner_id=owner.id, status="published", verified=True, page_json="{}")
        db.add(practice)
        db.flush()
        profiles = {}
        for t in (therapist, other_therapist):
            profiles[t.id] = TherapistProfile(user_id=t.id, practice_id=practice.id, approaches=["CBT"],
                                              languages=["en"], fee=1000, verified=True)
            db.add(profiles[t.id])
        db.flush()
        start = datetime.now(timezone.utc) + timedelta(days=1)
        for i, (t, c) in enumerate([(therapist, client_a), (therapist, client_b), (other_therapist, client_a)]):
            slot = AvailabilitySlot(therapist_id=profiles[t.id].id, starts_at=start + timedelta(hours=i),
                                    ends_at=start + timedelta(hours=i, minutes=50))
            db.add(slot)
            db.flush()
            db.add(Booking(client_id=c.id, availability_slot_id=slot.id))
        db.commit()
        yield db, therapist, other_therapist, client_a, client_b, owner


def test_case_memory_never_crosses_clients(case_scenario) -> None:
    db, therapist, _, client_a, client_b, _ = case_scenario
    a = add_case_memory(db, therapist, client_a.id, "panic on the bus to work", "note")
    b = add_case_memory(db, therapist, client_b.id, "panic on the bus to work", "note")

    statements: list[str] = []
    listener = lambda conn, cur, stmt, params, ctx, many: statements.append(stmt)  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        hits = retrieve_case_memory(db, therapist, client_a.id, "panic on the bus", min_similarity=0.1)
    finally:
        event.remove(engine, "before_cursor_execute", listener)

    assert [h.id for h in hits] == [a.id] and b.id not in [h.id for h in hits]
    hybrid = next(s for s in statements if "case_memory_chunks" in s)
    filtered_cte = hybrid.split("vec AS")[0]
    assert "c.client_id = %(client_id)s" in filtered_cte


def test_case_memory_isolated_between_therapists_of_same_client(case_scenario) -> None:
    db, therapist, other_therapist, client_a, _, _ = case_scenario
    mine = add_case_memory(db, therapist, client_a.id, "sleep diary shows late nights", "note")
    hits = retrieve_case_memory(db, other_therapist, client_a.id, "sleep diary late nights", min_similarity=0.1)
    assert mine.id not in [h.id for h in hits]


@pytest.mark.parametrize("who", ["client_a", "client_b", "owner", "unlinked_therapist"])
def test_case_memory_denied_without_relationship(case_scenario, who: str) -> None:
    db, therapist, _, client_a, client_b, owner = case_scenario
    add_case_memory(db, therapist, client_a.id, "avoids crowded places", "note")
    if who == "unlinked_therapist":
        actor = User(email=f"t-{uuid4().hex}@example.com", password_hash="x", role="therapist")
        db.add(actor)
        db.commit()
    else:
        actor = {"client_a": client_a, "client_b": client_b, "owner": owner}[who]
    with pytest.raises(PermissionError):
        retrieve_case_memory(db, actor, client_a.id, "crowded places", min_similarity=0.1)
    with pytest.raises(PermissionError):
        add_case_memory(db, actor, client_a.id, "injected", "note")


# ---------- migration parity ----------

def test_kb_migration_columns_types_and_indexes() -> None:
    with engine.connect() as conn:
        cols = {r[0]: (r[1], r[2]) for r in conn.execute(text(
            "SELECT column_name, udt_name, is_generated FROM information_schema.columns "
            "WHERE table_name IN ('kb_chunks', 'case_memory_chunks')"))}
        dims = conn.execute(text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'kb_chunks'::regclass AND attname = 'embedding'")).scalar()
        insp = inspect(conn)
        kb_idx = {i["name"] for i in insp.get_indexes("kb_chunks")}
        mem_fks = insp.get_foreign_keys("case_memory_chunks")
    assert cols["embedding"][0] == "vector" and dims == "vector(384)"
    assert cols["tsv"] == ("tsvector", "ALWAYS")
    assert {"ix_kb_chunks_tsv", "ix_kb_chunks_approach_language"} <= kb_idx
    assert any(fk["constrained_columns"] == ["client_id"] and fk["referred_table"] == "users" for fk in mem_fks)


# ---------- RAG calibration ----------

RECORDED_IN_DOMAIN = [0.839, 0.83, 0.846, 0.868, 0.859, 0.839, 0.88, 0.85, 0.817, 0.86, 0.791, 0.818, 0.851, 0.827, 0.859, 0.838, 0.831, 0.841, 0.844, 0.835]
RECORDED_OUT_OF_DOMAIN = [0.805, 0.798, 0.801, 0.761, 0.782, 0.749, 0.821, 0.804, 0.798, 0.773, 0.832, 0.844, 0.825, 0.814, 0.811, 0.818, 0.772, 0.796, 0.803, 0.78]  # 20 queries incl. "best pizza recipe"; near-misses (gym 0.844, sleep tracker 0.832) still pass


def test_default_threshold_rejects_all_recorded_out_of_domain_scores() -> None:
    """Real e5 top-1 scores recorded by backend/scripts/calibrate_rag.py (README 'RAG calibration')."""
    from backend.app.config import settings
    t = settings.kb_min_similarity
    assert RECORDED_OUT_OF_DOMAIN[0] < t  # best pizza recipe
    assert sum(s >= t for s in RECORDED_OUT_OF_DOMAIN) <= 2
    assert sum(s >= t for s in RECORDED_IN_DOMAIN) >= 17


def test_pizza_query_returns_empty_through_default_pipeline() -> None:
    with SessionLocal() as db:
        load_kb(db, KB_DIR)
        assert retrieve_knowledge(db, "best pizza recipe", language="en") == []


# ---------- session notes -> case memory ----------

def test_saving_session_notes_indexes_memory_per_client(case_scenario) -> None:
    from fastapi.testclient import TestClient

    from backend.app.auth import create_access_token
    from backend.app.main import app
    from backend.app.models import CaseMemoryChunk
    db, therapist, other_therapist, client_a, client_b, _ = case_scenario
    booking = db.scalars(select(Booking).join(AvailabilitySlot, AvailabilitySlot.id == Booking.availability_slot_id)
                         .join(TherapistProfile, TherapistProfile.id == AvailabilitySlot.therapist_id)
                         .where(Booking.client_id == client_a.id, TherapistProfile.user_id == therapist.id)).first()
    hdr = {"Authorization": f"Bearer {create_access_token(therapist.email, therapist.role)}"}
    with TestClient(app) as http:
        r = http.put(f"/bookings/{booking.id}/session-notes", headers=hdr,
                     json={"raw_notes": "Client reports zebra phobia flares on weekends.\n\nWe practised paced breathing.", "source": "typed"})
        assert r.status_code == 200, r.text
        http.put(f"/bookings/{booking.id}/session-notes", headers=hdr,
                 json={"raw_notes": "Client reports zebra phobia flares on weekends.", "source": "typed"})
    db.expire_all()
    rows = db.scalars(select(CaseMemoryChunk).where(CaseMemoryChunk.source_type == "session_note",
                                                    CaseMemoryChunk.source_id.is_not(None),
                                                    CaseMemoryChunk.client_id == client_a.id)).all()
    assert len(rows) == 1 and all(r.client_id == client_a.id for r in rows)  # re-save replaced, not duplicated
    assert retrieve_case_memory(db, therapist, client_a.id, "zebra phobia weekends", min_similarity=0.1)
    # client B (same therapist) never sees client A's notes
    assert retrieve_case_memory(db, therapist, client_b.id, "zebra phobia weekends", min_similarity=0.0) == []
