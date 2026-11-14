"""Knowledge base loading and hybrid retrieval (filter -> pgvector + full-text -> RRF -> threshold)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.auth import therapist_has_client
from backend.app.config import settings
from backend.app.embeddings import get_embedder
from backend.app.models import CaseMemoryChunk, KbChunk, KbDocument, User

APPROACHES = {"CBT", "DBT", "CBT-I", "PM+", "general"}
REQUIRED_SECTIONS = ("Purpose", "Typically used when", "Cautions / when NOT to use", "Steps",
                     "Also described as")
LICENCE = "original, for demo"
RRF_K = 60
CANDIDATE_POOL = 20


@dataclass(frozen=True)
class Retrieved:
    id: int
    text: str
    similarity: float
    rrf_score: float
    title: str | None = None
    approach: str | None = None
    language: str | None = None


# ---------- loading ----------

def parse_kb_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: missing front matter")
    meta: dict[str, str | None] = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        meta[key.strip()] = None if value in ("", "null") else value
    for key in ("title", "approach", "language", "source_inspired_by", "reviewed_by"):
        if not meta.get(key):
            raise ValueError(f"{path.name}: missing {key}")
    if meta["approach"] not in APPROACHES:
        raise ValueError(f"{path.name}: bad approach {meta['approach']}")
    body = m.group(2).strip()
    for section in REQUIRED_SECTIONS:
        if f"## {section}" not in body:
            raise ValueError(f"{path.name}: missing section {section}")
    return {
        "slug": re.sub(r"^\d+-", "", path.stem),
        "title": meta["title"], "approach": meta["approach"], "language": meta["language"],
        "source_inspired_by": meta["source_inspired_by"], "reviewed_by": meta["reviewed_by"],
        "reviewed_at": datetime.fromisoformat(meta["reviewed_at"]) if meta.get("reviewed_at") else None,
        "body": body, "content_hash": hashlib.sha256(raw.encode()).hexdigest(),
    }


def load_kb(db: Session, kb_dir: str | Path = settings.kb_dir, force: bool = False) -> dict[str, int]:
    """Idempotent: one chunk per entry; unchanged files are not re-embedded."""
    entries = [parse_kb_file(p) for p in sorted(Path(kb_dir).glob("*.md"))]
    existing = {d.slug: d for d in db.scalars(select(KbDocument).where(KbDocument.slug.in_([e["slug"] for e in entries])))}
    changed = [e for e in entries if force or e["slug"] not in existing or existing[e["slug"]].content_hash != e["content_hash"]]
    chunk_texts = [f"{e['title']}\n\n{e['body']}" for e in changed]
    vectors = get_embedder().embed_passages(chunk_texts) if changed else []
    for entry, chunk_text, vector in zip(changed, chunk_texts, vectors):
        doc = existing.get(entry["slug"]) or KbDocument(slug=entry["slug"])
        for key in ("title", "approach", "language", "source_inspired_by", "reviewed_by", "reviewed_at", "body", "content_hash"):
            setattr(doc, key, entry[key])
        doc.licence = LICENCE
        doc.updated_at = datetime.now(timezone.utc)
        db.add(doc)
        db.flush()
        db.query(KbChunk).filter(KbChunk.document_id == doc.id).delete()
        db.add(KbChunk(document_id=doc.id, text=chunk_text, approach=entry["approach"],
                       language=entry["language"], topic_tags=[entry["slug"]], embedding=vector))
    db.commit()
    return {"files": len(entries), "embedded": len(changed)}


# ---------- retrieval ----------

def _vec_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def _or_tsquery(query: str) -> str:
    return " | ".join(dict.fromkeys(re.findall(r"[^\W_]+", query.lower())))


_HYBRID_SQL = """
WITH filtered AS (
    SELECT {cols} FROM {table} c WHERE {where}
),
vec AS (
    SELECT id, row_number() OVER (ORDER BY dist) AS rnk FROM (
        SELECT id, embedding <=> CAST(:qvec AS vector) AS dist FROM filtered
        ORDER BY dist LIMIT :pool
    ) v
),
lex AS (
    SELECT id, row_number() OVER (ORDER BY score DESC) AS rnk FROM (
        SELECT f.id, ts_rank_cd(f.tsv, tq) AS score
        FROM filtered f, to_tsquery('english', :tsq) tq
        WHERE :tsq <> '' AND f.tsv @@ tq
        ORDER BY score DESC LIMIT :pool
    ) l
)
SELECT f.*, 1 - (f.embedding <=> CAST(:qvec AS vector)) AS similarity,
       COALESCE(1.0 / ({rrf_k} + vec.rnk), 0) + COALESCE(1.0 / ({rrf_k} + lex.rnk), 0) AS rrf_score
FROM filtered f
LEFT JOIN vec ON vec.id = f.id
LEFT JOIN lex ON lex.id = f.id
WHERE (vec.id IS NOT NULL OR lex.id IS NOT NULL)
  AND 1 - (f.embedding <=> CAST(:qvec AS vector)) >= :min_sim
ORDER BY rrf_score DESC, similarity DESC
LIMIT :k
"""


def _hybrid(db: Session, *, table: str, cols: str, where: str, params: dict, query: str,
            k: int, min_similarity: float | None) -> list:
    sql = _HYBRID_SQL.format(table=table, cols=cols, where=where, rrf_k=RRF_K)
    return db.execute(text(sql), {
        **params,
        "qvec": _vec_literal(get_embedder().embed_query(query)),
        "tsq": _or_tsquery(query),
        "pool": CANDIDATE_POOL, "k": k,
        "min_sim": settings.kb_min_similarity if min_similarity is None else min_similarity,
    }).mappings().all()


def retrieve_knowledge(db: Session, query: str, approach: str | None = None, language: str | None = None,
                       k: int = 5, min_similarity: float | None = None) -> list[Retrieved]:
    rows = _hybrid(
        db, table="kb_chunks", query=query, k=k, min_similarity=min_similarity,
        cols="c.id, c.text, c.approach, c.language, c.embedding, c.tsv, "
             "(SELECT d.title FROM kb_documents d WHERE d.id = c.document_id) AS title",
        where="(CAST(:approach AS text) IS NULL OR c.approach = :approach) "
              "AND (CAST(:language AS text) IS NULL OR c.language = :language)",
        params={"approach": approach, "language": language},
    )
    return [Retrieved(id=r["id"], text=r["text"], similarity=float(r["similarity"]), rrf_score=float(r["rrf_score"]),
                      title=r["title"], approach=r["approach"], language=r["language"]) for r in rows]


# ---------- per-client case memory ----------

def _require_case_access(db: Session, user: User, client_id: int) -> None:
    if user.role != "therapist" or not therapist_has_client(db, user.id, client_id):
        raise PermissionError("No case-memory access for this client")


def add_case_memory(db: Session, user: User, client_id: int, text_: str, source_type: str,
                    source_id: int | None = None) -> CaseMemoryChunk:
    _require_case_access(db, user, client_id)
    row = CaseMemoryChunk(client_id=client_id, therapist_user_id=user.id, source_type=source_type,
                          source_id=source_id, text=text_, embedding=get_embedder().embed_passages([text_])[0])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _chunk_notes(notes: str, max_chars: int = 600) -> list[str]:
    chunks, cur = [], ""
    for para in re.split(r"\n\s*\n|(?<=[.!?])\s+", notes.strip()):
        para = para.strip()
        if not para:
            continue
        if cur and len(cur) + len(para) + 1 > max_chars:
            chunks.append(cur)
            cur = ""
        cur = f"{cur} {para}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def index_session_notes(db: Session, user: User, client_id: int, session_id: int, notes: str) -> int:
    """Replace this session's memory chunks with fresh embeddings. Caller commits."""
    _require_case_access(db, user, client_id)
    db.query(CaseMemoryChunk).filter(CaseMemoryChunk.source_type == "session_note",
                                     CaseMemoryChunk.source_id == session_id).delete()
    chunks = _chunk_notes(notes)
    vectors = get_embedder().embed_passages(chunks) if chunks else []
    for chunk, vector in zip(chunks, vectors):
        db.add(CaseMemoryChunk(client_id=client_id, therapist_user_id=user.id, source_type="session_note",
                               source_id=session_id, text=chunk, embedding=vector))
    return len(chunks)


def retrieve_case_memory(db: Session, user: User, client_id: int, query: str, k: int = 5,
                         min_similarity: float | None = None) -> list[Retrieved]:
    """client_id (and the requesting therapist) are filtered inside the SQL, before ranking."""
    _require_case_access(db, user, client_id)
    rows = _hybrid(
        db, table="case_memory_chunks", query=query, k=k, min_similarity=min_similarity,
        cols="c.id, c.text, c.embedding, c.tsv",
        where="c.client_id = :client_id AND c.therapist_user_id = :therapist_user_id",
        params={"client_id": client_id, "therapist_user_id": user.id},
    )
    return [Retrieved(id=r["id"], text=r["text"], similarity=float(r["similarity"]),
                      rrf_score=float(r["rrf_score"])) for r in rows]
