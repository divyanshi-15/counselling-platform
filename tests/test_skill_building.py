from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from backend.app import reminders
from backend.app.agents import copilot
from backend.app.db import SessionLocal
from backend.app.models import (Alert, JournalEntry, JourneyAssignment, JourneyStep, MoodCheckin, PendingAction, ReminderLog,
                                User)
from test_copilot import _h, world  # noqa: F401  (world is a fixture)

TODAY = datetime.now(timezone.utc).date()
MOOD = {"mood": 4, "sleep_hours": 7.5, "note": "Felt calmer after a walk."}
STEPS = [{"week": 1, "exercise": "worry_postponement", "text_en": "Set a worry time.", "text_hi": "चिंता-समय तय करें।"},
         {"week": 2, "exercise": "thought_record", "text_en": "Write one thought record."}]
PROGRAMME = {"title_en": "Settling worry", "title_hi": "चिंता को शांत करना", "steps": STEPS}


class Model:
    def __init__(self, *outputs):
        self.outputs, self.calls = list(outputs), []

    def __call__(self, system, blocks, *, max_tokens):
        assert max_tokens > 0
        self.calls.append((system, blocks))
        out = self.outputs.pop(0)
        return out if out is None or isinstance(out, str) else json.dumps(out)


def _alerts(client_id):
    with SessionLocal() as db:
        return db.query(Alert).filter(Alert.client_id == client_id).all()


def _key():
    return {"Idempotency-Key": uuid4().hex}


# ---------- mood check-in ----------

def test_mood_upsert_is_one_row_per_day(world) -> None:
    client, w = world
    h = _h(w["ca"])
    r = client.put("/client/mood", headers=h, json=MOOD)
    assert r.status_code == 200 and r.json()["status"] == "saved" and r.json()["entry"]["mood"] == 4
    assert "Skill-building support" in r.json()["notice"]
    r = client.put("/client/mood", headers=h, json=MOOD | {"mood": 2, "note": None})
    assert r.json()["entry"]["mood"] == 2 and r.json()["entry"]["note"] is None
    items = client.get("/client/mood", headers=h).json()["items"]
    assert len(items) == 1 and items[0]["mood"] == 2
    assert client.put("/client/mood", headers=h, json=MOOD | {"mood": 6}).status_code == 422
    assert client.put("/client/mood", headers=h, json=MOOD | {"note": "x" * 501}).status_code == 422
    assert client.put("/client/mood", headers=h, json=MOOD | {"entry_date": str(TODAY - timedelta(days=5))}).status_code == 422


def test_mood_note_crisis_stops_saves_nothing_alerts_therapist(world, monkeypatch) -> None:
    client, w = world
    model = Model()
    monkeypatch.setattr(copilot, "call_model", model)
    note = {"mood": 1, "sleep_hours": 3, "note": "I want to end my life"}
    r = client.put("/client/mood", headers=_h(w["ca"]), json=note)
    assert r.status_code == 200 and r.json()["status"] == "crisis" and "14416" in r.json()["message"]
    assert r.json()["entry"] is None and model.calls == []
    assert client.get("/client/mood", headers=_h(w["ca"])).json()["items"] == []
    (alert,) = _alerts(w["ca"].id)
    assert alert.priority == "high" and alert.therapist_user_id == w["ta"].id and alert.payload["source"] == "mood_checkin"
    client.put("/client/mood", headers=_h(w["ca"]), json=note)  # identical resubmission: still one alert
    assert len(_alerts(w["ca"].id)) == 1
    with SessionLocal() as db:
        db.query(User).filter(User.id == w["ca"].id).update({"language": "hi"})
        db.commit()
    assert "14416" in client.put("/client/mood", headers=_h(w["ca"]), json=note).json()["message"]


def test_mood_access_control(world) -> None:
    client, w = world
    client.put("/client/mood", headers=_h(w["ca"]), json=MOOD)
    for user in (w["ta"], w["owner"]):
        assert client.put("/client/mood", headers=_h(user), json=MOOD).status_code == 403
        assert client.get("/client/mood", headers=_h(user)).status_code == 403
    assert client.get("/client/mood").status_code == 401
    assert client.get("/client/mood", headers=_h(w["cb"])).json()["items"] == []  # cross-client
    url = f"/clients/{w['ca'].id}/mood-trend"
    for user in (w["tb"], w["owner"], w["ca"], w["cb"]):  # cross-therapist, owner -> clinical, clients
        assert client.get(url, headers=_h(user)).status_code == 403
    body = client.get(url, headers=_h(w["ta"])).json()
    assert body["count"] == 1 and body["entries"][0]["mood"] == 4 and "note" not in body["entries"][0]


def test_briefing_carries_mood_trend(world, monkeypatch) -> None:
    client, w = world
    monkeypatch.setattr(copilot, "call_model", Model(None, None, None, None))
    for i in range(3):
        with SessionLocal() as db:
            db.add(MoodCheckin(client_id=w["ca"].id, entry_date=TODAY - timedelta(days=i), mood=3 + i % 2, sleep_hours=6.0))
            db.add(MoodCheckin(client_id=w["ca"].id, entry_date=TODAY - timedelta(days=40 + i), mood=1, sleep_hours=4.0))
            db.commit()
    with SessionLocal() as db:
        briefing, _ = copilot.run_copilot_for_client(db, therapist_user_id=w["ta"].id, client_id=w["ca"].id,
                                                     session_starts_at="2026-01-01T00:00:00+00:00")
    assert briefing.mood_trend["count"] == 3 and briefing.mood_trend["avg_sleep"] == 6.0  # 14-day window only


# ---------- journal ----------

def test_journal_private_by_default_and_shared_by_choice(world) -> None:
    client, w = world
    h = _h(w["ca"])
    first = client.post("/client/journal", headers=h | _key(), json={"text": "Private thought."}).json()["entry"]
    second = client.post("/client/journal", headers=h | _key(), json={"text": "Share this one.", "shared": True}).json()["entry"]
    assert first["shared"] is False and second["shared"] is True
    assert [e["text"] for e in client.get("/client/journal", headers=h).json()["items"]] == ["Share this one.", "Private thought."]
    seen = client.get(f"/clients/{w['ca'].id}/journal", headers=_h(w["ta"])).json()["items"]
    assert [e["text"] for e in seen] == ["Share this one."]
    assert client.patch(f"/client/journal/{first['id']}", headers=h, json={"shared": True}).json()["shared"] is True
    assert len(client.get(f"/clients/{w['ca'].id}/journal", headers=_h(w["ta"])).json()["items"]) == 2
    client.patch(f"/client/journal/{first['id']}", headers=h, json={"shared": False})
    assert len(client.get(f"/clients/{w['ca'].id}/journal", headers=_h(w["ta"])).json()["items"]) == 1
    assert client.post("/client/journal", headers=h | _key(), json={"text": "x" * 2001}).status_code == 422


def test_journal_idempotent_and_crisis(world, monkeypatch) -> None:
    client, w = world
    model = Model()
    monkeypatch.setattr(copilot, "call_model", model)
    h = _h(w["ca"]) | _key()
    a = client.post("/client/journal", headers=h, json={"text": "Once."}).json()["entry"]
    b = client.post("/client/journal", headers=h, json={"text": "Once."}).json()["entry"]
    assert a["id"] == b["id"]
    with SessionLocal() as db:
        assert db.query(JournalEntry).filter(JournalEntry.client_id == w["ca"].id).count() == 1
    r = client.post("/client/journal", headers=_h(w["ca"]) | _key(), json={"text": "I want to end my life", "shared": True})
    assert r.json()["status"] == "crisis" and "14416" in r.json()["message"] and r.json()["entry"] is None
    with SessionLocal() as db:
        assert db.query(JournalEntry).filter(JournalEntry.client_id == w["ca"].id).count() == 1
    (alert,) = _alerts(w["ca"].id)
    assert alert.priority == "high" and alert.payload["source"] == "journal" and model.calls == []


def test_journal_access_control(world) -> None:
    client, w = world
    entry = client.post("/client/journal", headers=_h(w["ca"]) | _key(), json={"text": "Mine.", "shared": True}).json()["entry"]
    for user in (w["ta"], w["owner"]):
        assert client.post("/client/journal", headers=_h(user) | _key(), json={"text": "x"}).status_code == 403
        assert client.get("/client/journal", headers=_h(user)).status_code == 403
        assert client.patch(f"/client/journal/{entry['id']}", headers=_h(user), json={"shared": False}).status_code == 403
    assert client.patch(f"/client/journal/{entry['id']}", headers=_h(w["cb"]), json={"shared": False}).status_code == 403
    assert client.get("/client/journal", headers=_h(w["cb"])).json()["items"] == []
    assert client.post("/client/journal", headers=_key(), json={"text": "x"}).status_code == 401
    url = f"/clients/{w['ca'].id}/journal"
    for user in (w["tb"], w["owner"], w["ca"], w["cb"]):
        assert client.get(url, headers=_h(user)).status_code == 403


# ---------- journeys ----------

def _assign(client, w, programme=PROGRAMME, who="ta", target="ca"):
    return client.post(f"/clients/{w[target].id}/journeys", headers=_h(w[who]) | _key(), json={"programme": programme})


def test_assign_and_client_completes_steps(world) -> None:
    client, w = world
    r = _assign(client, w)
    assert r.status_code == 200
    aid = r.json()["assignment_id"]
    (j,) = client.get("/client/journeys", headers=_h(w["ca"])).json()["items"]
    assert j["title"] == "Settling worry" and j["current_week"] == 1 and j["total"] == 2 and j["completed"] == 0
    assert [s["text"] for s in j["current_steps"]] == ["Set a worry time."]
    step = j["current_steps"][0]["id"]
    done = client.post(f"/client/journeys/{aid}/steps/{step}/complete", headers=_h(w["ca"])).json()
    again = client.post(f"/client/journeys/{aid}/steps/{step}/complete", headers=_h(w["ca"])).json()
    assert done["completed"] == again["completed"] == 1 and done["current_steps"][0]["done"] is True
    later = next(s for s in client.get("/therapists/me/journeys", headers=_h(w["ta"])).json()["items"]
                 if s["own"])["steps"]
    assert len(later) == 2
    with SessionLocal() as db:  # week-2 step is not open yet
        week2 = db.query(JourneyStep).filter(JourneyStep.week == 2).order_by(JourneyStep.id.desc()).first().id
    assert client.post(f"/client/journeys/{aid}/steps/{week2}/complete", headers=_h(w["ca"])).status_code == 409
    with SessionLocal() as db:  # a week later it opens, and Hindi text is used for a Hindi client
        db.query(JourneyAssignment).filter(JourneyAssignment.id == aid).update({"started_on": TODAY - timedelta(days=8)})
        db.query(User).filter(User.id == w["ca"].id).update({"language": "hi"})
        db.commit()
    (j,) = client.get("/client/journeys", headers=_h(w["ca"])).json()["items"]
    assert j["current_week"] == 2 and j["title"] == "चिंता को शांत करना"
    assert client.post(f"/client/journeys/{aid}/steps/{week2}/complete", headers=_h(w["ca"])).json()["completed"] == 2
    seen = client.get(f"/clients/{w['ca'].id}/journeys", headers=_h(w["ta"])).json()["items"]
    assert seen[0]["completed"] == 2 and seen[0]["total"] == 2


def test_assign_is_idempotent_and_validates(world) -> None:
    client, w = world
    h = _h(w["ta"]) | _key()
    a = client.post(f"/clients/{w['ca'].id}/journeys", headers=h, json={"programme": PROGRAMME}).json()
    b = client.post(f"/clients/{w['ca'].id}/journeys", headers=h, json={"programme": PROGRAMME}).json()
    assert a == b and len(client.get("/client/journeys", headers=_h(w["ca"])).json()["items"]) == 1
    bad = PROGRAMME | {"steps": [STEPS[0] | {"exercise": "nope"}]}
    assert _assign(client, w, bad).status_code == 422
    assert _assign(client, w, PROGRAMME | {"steps": [STEPS[1]]}).status_code == 422  # week 1 missing
    assert client.post(f"/clients/{w['ca'].id}/journeys", headers=h, json={}).status_code == 422
    assert client.post(f"/clients/{w['ca'].id}/journeys", headers=_h(w["ta"]), json={"programme": PROGRAMME}).status_code == 422  # no key


def test_assign_library_template(world) -> None:
    client, w = world
    lib = client.get("/therapists/me/journeys", headers=_h(w["ta"])).json()
    assert {e["slug"] for e in lib["exercises"]} >= {"worry_postponement", "thought_record"}
    template = next((j for j in lib["items"] if not j["own"]), None)
    if template is None:  # fresh test database: the seed has not run
        return
    assert client.post(f"/clients/{w['ca'].id}/journeys", headers=_h(w["ta"]) | _key(), json={"template_id": template["id"]}).status_code == 200


def test_journey_access_control(world) -> None:
    client, w = world
    aid = _assign(client, w).json()["assignment_id"]
    with SessionLocal() as db:
        step = db.query(JourneyStep).filter_by(week=1).order_by(JourneyStep.id.desc()).first().id
    assert _assign(client, w, who="tb").status_code == 403  # cross-therapist
    assert _assign(client, w, who="owner").status_code == 403  # owner -> clinical
    assert _assign(client, w, who="ca").status_code == 403
    assert client.post(f"/clients/{w['ca'].id}/journeys/draft", headers=_h(w["tb"]) | _key(), json={"focus": "worry"}).status_code == 403
    assert client.post(f"/clients/{w['ca'].id}/journeys/draft", headers=_h(w["owner"]) | _key(), json={"focus": "worry"}).status_code == 403
    for user in (w["tb"], w["owner"], w["ca"], w["cb"]):
        assert client.get(f"/clients/{w['ca'].id}/journeys", headers=_h(user)).status_code == 403
    assert client.post(f"/client/journeys/{aid}/steps/{step}/complete", headers=_h(w["cb"])).status_code == 403  # cross-client
    for user in (w["ta"], w["owner"]):
        assert client.post(f"/client/journeys/{aid}/steps/{step}/complete", headers=_h(user)).status_code == 403
        assert client.get("/client/journeys", headers=_h(user)).status_code == 403
    assert client.get("/client/journeys", headers=_h(w["cb"])).json()["items"] == []
    assert client.get("/therapists/me/journeys", headers=_h(w["owner"])).status_code == 403
    assert client.get("/therapists/me/journeys", headers=_h(w["ca"])).status_code == 403
    mine = {j["id"] for j in client.get("/therapists/me/journeys", headers=_h(w["ta"])).json()["items"] if j["own"]}
    theirs = {j["id"] for j in client.get("/therapists/me/journeys", headers=_h(w["tb"])).json()["items"] if j["own"]}
    assert mine and not (mine & theirs)  # a therapist's own programmes are not in another's library


def _approve(client, user, action):
    return client.post(f"/pending-actions/{action.id}/approve", headers=_h(user) | {"Idempotency-Key": action.idempotency_key})


def _drafts(client_id):
    with SessionLocal() as db:
        return [a for a in db.query(PendingAction).filter(PendingAction.type == "journey_draft").all()
                if a.payload["client_id"] == client_id]


def test_ai_draft_is_pending_until_therapist_approves(world, monkeypatch) -> None:
    client, w = world
    model = Model(PROGRAMME)
    monkeypatch.setattr(copilot, "call_model", model)
    h = _h(w["ta"]) | _key()
    r = client.post(f"/clients/{w['ca'].id}/journeys/draft", headers=h, json={"focus": "worry at night", "weeks": 2})
    assert r.json()["status"] == "drafted" and len(model.calls) == 1
    assert "<<<CLIENT_DATA>>>" in model.calls[0][1][1][0]
    assert client.post(f"/clients/{w['ca'].id}/journeys/draft", headers=h, json={"focus": "worry at night"}).json()["pending_action_id"] == r.json()["pending_action_id"]
    assert len(model.calls) == 1  # replay makes no second model call
    (action,) = _drafts(w["ca"].id)
    assert client.get("/client/journeys", headers=_h(w["ca"])).json()["items"] == []  # nothing applied yet
    inbox = client.get("/therapists/me/pending-actions", headers=_h(w["ta"])).json()["items"]
    item = next(i for i in inbox if i["id"] == action.id)
    assert item["client_view"]["kind"] == "journey" and item["client_view"]["fields"][0].startswith("Week 1")
    edit = PROGRAMME | {"title_en": "Edited worry programme"}
    assert client.put(f"/pending-actions/{action.id}/journey-draft", headers=_h(w["tb"]), json=edit).status_code == 403
    assert client.put(f"/pending-actions/{action.id}/journey-draft", headers=_h(w["owner"]), json=edit).status_code == 403
    assert client.put(f"/pending-actions/{action.id}/journey-draft", headers=_h(w["ta"]), json=edit | {"title_en": "Take a supplement"}).status_code == 422
    assert client.put(f"/pending-actions/{action.id}/journey-draft", headers=_h(w["ta"]), json=edit).status_code == 200
    for user in (w["tb"], w["owner"], w["ca"]):
        assert _approve(client, user, action).status_code == 403
    assert _approve(client, w["ta"], action).status_code == 200
    assert _approve(client, w["ta"], action).status_code == 200  # replay
    (j,) = client.get("/client/journeys", headers=_h(w["ca"])).json()["items"]
    assert j["title"] == "Edited worry programme"
    assert client.put(f"/pending-actions/{action.id}/journey-draft", headers=_h(w["ta"]), json=edit).status_code == 409


def test_ai_draft_postcheck_retry_and_unavailable(world, monkeypatch) -> None:
    client, w = world
    url = f"/clients/{w['ca'].id}/journeys/draft"
    bad = PROGRAMME | {"steps": [STEPS[0] | {"text_en": "This is a diagnosis of anxiety disorder."}, STEPS[1]]}
    model = Model(bad, PROGRAMME)  # first draft is rejected by the post-check, the retry passes
    monkeypatch.setattr(copilot, "call_model", model)
    assert client.post(url, headers=_h(w["ta"]) | _key(), json={"focus": "worry"}).json()["status"] == "drafted"
    assert len(model.calls) == 2 and "invalid" in model.calls[1][1][-1][0]
    monkeypatch.setattr(copilot, "call_model", Model(bad, bad))
    r = client.post(url, headers=_h(w["ta"]) | _key(), json={"focus": "worry"})
    assert r.json()["status"] == "error" and r.json()["pending_action_id"] is None
    monkeypatch.setattr(copilot, "call_model", Model("not json", PROGRAMME | {"steps": [STEPS[0] | {"exercise": "made_up"}]}))
    assert client.post(url, headers=_h(w["ta"]) | _key(), json={"focus": "worry"}).json()["status"] == "error"
    monkeypatch.setattr(copilot, "call_model", Model(None))
    assert client.post(url, headers=_h(w["ta"]) | _key(), json={"focus": "worry"}).json()["status"] == "ai_unavailable"
    assert len(_drafts(w["ca"].id)) == 1


# ---------- insights ----------

def test_insights_plain_numbers_and_access(world) -> None:
    client, w = world
    for i in (0, 3, 10):
        with SessionLocal() as db:
            db.add(MoodCheckin(client_id=w["ca"].id, entry_date=TODAY - timedelta(days=i), mood=3 + i % 2, sleep_hours=6.5))
            db.commit()
    r = client.get("/client/insights", headers=_h(w["ca"])).json()
    assert len(r["series"]) == 30 and r["series"][-1]["date"] == TODAY.isoformat()
    assert r["checkins"] == 3 and r["avg_sleep"] == 6.5 and r["exercises_completed"] == 0
    assert "Skill-building support" in r["notice"]
    assert client.get("/client/insights", headers=_h(w["cb"])).json()["checkins"] == 0  # cross-client
    for user in (w["ta"], w["owner"]):
        assert client.get("/client/insights", headers=_h(user)).status_code == 403
    assert client.get("/client/insights").status_code == 401


# ---------- reminders ----------

def test_reminders_off_by_default_and_owner_only(world) -> None:
    client, w = world
    assert client.get("/client/reminders", headers=_h(w["ca"])).json()["daily_checkin"] is False
    r = client.put("/client/reminders", headers=_h(w["ca"]), json={"daily_checkin": True, "exercise_nudges": False})
    assert r.json() == r.json() | {"daily_checkin": True, "exercise_nudges": False}
    assert client.get("/client/reminders", headers=_h(w["cb"])).json()["daily_checkin"] is False  # cross-client
    for user in (w["ta"], w["owner"]):
        assert client.get("/client/reminders", headers=_h(user)).status_code == 403
        assert client.put("/client/reminders", headers=_h(user), json={"daily_checkin": True, "exercise_nudges": True}).status_code == 403


def test_reminder_sends_are_idempotent_and_opt_in(world, monkeypatch) -> None:
    client, w = world
    sent = []
    monkeypatch.setattr(reminders, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or "sent")
    mine = lambda: [m for m in sent if m[0] == w["ca"].email]  # noqa: E731  (other tests leave opted-in clients behind)
    day = date(2026, 6, 10)
    with SessionLocal() as db:
        reminders.run_reminders(db, day)
    assert mine() == []  # not opted in
    client.put("/client/reminders", headers=_h(w["ca"]), json={"daily_checkin": True, "exercise_nudges": False})
    with SessionLocal() as db:
        reminders.run_reminders(db, day)
        reminders.run_reminders(db, day)  # same day, same key: no second send
        assert len(mine()) == 1
        reminders.run_reminders(db, day + timedelta(days=1))
    assert len(mine()) == 2
    text = " ".join(" ".join(s[1:]) for s in mine()).lower()
    assert "streak" not in text and "missed" not in text and "forgot" not in text
    with SessionLocal() as db:
        db.add(MoodCheckin(client_id=w["ca"].id, entry_date=day + timedelta(days=2), mood=3, sleep_hours=6))
        db.commit()
        reminders.run_reminders(db, day + timedelta(days=2))  # already checked in today
        assert len(mine()) == 2
        assert db.query(ReminderLog).filter(ReminderLog.client_id == w["ca"].id).count() == 2
    client.put("/client/reminders", headers=_h(w["ca"]), json={"daily_checkin": False, "exercise_nudges": False})
    with SessionLocal() as db:
        reminders.run_reminders(db, day + timedelta(days=3))
    assert len(mine()) == 2  # turned off by the client
