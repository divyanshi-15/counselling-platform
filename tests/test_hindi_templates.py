from __future__ import annotations

import re

from test_copilot import _h, world  # noqa: F401

from backend.app.db import SessionLocal
from backend.app.exercises import template_for
from backend.app.models import Exercise

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def test_every_seeded_exercise_has_hindi_template() -> None:
    with SessionLocal() as db:
        rows = db.query(Exercise).all()
    assert rows
    for e in rows:
        assert e.title_hi and DEVANAGARI.search(e.title_hi), e.slug
        assert e.template_hi and DEVANAGARI.search(e.template_hi["intro"]), e.slug
        en, hi = e.template_en["fields"], e.template_hi["fields"]
        assert [(f["id"], f["type"], f["required"]) for f in en] == [(f["id"], f["type"], f["required"]) for f in hi]
        assert all(DEVANAGARI.search(f["label"]) for f in hi)


def test_english_fallback_when_hindi_missing() -> None:
    e = Exercise(slug="x", title_en="T", template_en={"intro": "i", "fields": []})
    assert template_for(e, "hi") == ("T", {"intro": "i", "fields": []})


def test_client_language_preference_selects_template(world) -> None:
    from backend.app.models import Assignment, PendingAction
    client, w = world
    with SessionLocal() as db:
        ex = db.query(Exercise).filter(Exercise.slug == "worry_postponement").one()
        pa = PendingAction(practice_id=w["practice"].id, type="release_exercise", status="approved",
                           idempotency_key=f"hi:{w['ca'].id}", payload={}, assignee_user_id=w["ta"].id)
        db.add(pa)
        db.flush()
        a = Assignment(client_id=w["ca"].id, therapist_user_id=w["ta"].id, exercise_id=ex.id, pending_action_id=pa.id,
                       status="assigned")
        db.add(a)
        db.commit()
        aid = a.id
    url = f"/client/assignments/{aid}/exercise"
    assert client.get(url, headers=_h(w["ca"])).json()["template"]["intro"].startswith("Write every worry")
    with SessionLocal() as db:
        db.query(type(w["ca"])).filter_by(id=w["ca"].id).update({"language": "hi"})
        db.commit()
    body = client.get(url, headers=_h(w["ca"])).json()
    assert DEVANAGARI.search(body["title"]) and DEVANAGARI.search(body["template"]["intro"])
    assert client.get(url + "?lang=en", headers=_h(w["ca"])).json()["title"].startswith("Worry")
