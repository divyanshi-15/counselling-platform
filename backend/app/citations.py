"""Citation validator for copilot suggestions. Deterministic: the model's own label is never trusted."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

NO_SUPPORT = "no supporting entry found"


class Suggestion(BaseModel):
    text: str
    chunk_ids: list[int] = Field(default_factory=list)
    note_quotes: list[str] = Field(default_factory=list)
    label: Literal["SUPPORTED", "INFERRED"] | None = None
    support_note: str | None = None


class CitationError(ValueError):
    pass


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def validate_suggestions(suggestions: list[Suggestion], retrieved_ids: set[int] | list[int],
                         notes_text: str | None = None) -> list[Suggestion]:
    """Reject fabricated chunk ids or quotes; label anything without valid support INFERRED."""
    retrieved = set(retrieved_ids)
    notes = _norm(notes_text or "")
    out: list[Suggestion] = []
    for s in suggestions:
        fabricated = sorted(set(s.chunk_ids) - retrieved)
        if fabricated:
            raise CitationError(f"Suggestion cites chunk ids that were not retrieved: {fabricated}")
        bad_quotes = [q for q in s.note_quotes if not q.strip() or _norm(q) not in notes]
        if bad_quotes:
            raise CitationError(f"Suggestion quotes text not found in the client's notes: {bad_quotes}")
        supported = bool(s.chunk_ids or s.note_quotes)
        out.append(s.model_copy(update={
            "label": "SUPPORTED" if supported else "INFERRED",
            "support_note": None if supported or retrieved else NO_SUPPORT,
        }))
    return out
