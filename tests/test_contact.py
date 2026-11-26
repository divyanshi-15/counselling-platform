from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app.auth import create_access_token, hash_password
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import ContactMessage, User
from backend.app.safety import CRISIS_MESSAGE

client = TestClient(app)
TAG = "ctt" + uuid4().hex[:8]


def body(**kw):
    return {"name": "Asha Rao", "email": "asha@example.com", "message": f"{TAG} Do you offer evening sessions?"} | kw


def post(key=None, **kw):
    return client.post("/contact", headers={"Idempotency-Key": key or uuid4().hex}, json=body(**kw))


def rows():
    with SessionLocal() as db:
        return db.query(ContactMessage).filter(ContactMessage.message.like(f"{TAG}%")).all()


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k, v in {"SMTP_HOST": "smtp.test", "SMTP_PORT": "465", "SMTP_USER": "box@test.in", "SMTP_PASS": "s3cret-pass",
                 "SMTP_FROM": "box@test.in", "SMTP_SECURE": "ssl", "CONTACT_TO": "inbox@test.in"}.items():
        monkeypatch.setenv(k, v)
    yield
    with SessionLocal() as db:
        db.execute(delete(ContactMessage).where(ContactMessage.message.like(f"{TAG}%")))
        db.commit()


@pytest.fixture
def smtp():
    conn = MagicMock()
    conn.__enter__.return_value = conn
    with patch("backend.app.contact.smtplib.SMTP_SSL", return_value=conn) as ssl, patch("backend.app.contact.smtplib.SMTP", return_value=conn) as plain:
        conn.ssl, conn.plain = ssl, plain
        yield conn


def test_saved_and_sent(smtp):
    r = post()
    assert r.status_code == 200 and r.json()["status"] == "received"
    [row] = rows()
    assert row.email_status == "sent" and not row.high_priority
    smtp.ssl.assert_called_once()
    smtp.login.assert_called_once_with("box@test.in", "s3cret-pass")
    msg = smtp.send_message.call_args[0][0]
    assert msg["To"] == "inbox@test.in" and msg["Reply-To"] == "asha@example.com" and msg["From"] == "box@test.in"
    assert not msg.is_multipart() and msg.get_content_type() == "text/plain" and TAG in msg.get_content()


def test_starttls_mode(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_SECURE", "starttls")
    monkeypatch.setenv("SMTP_PORT", "587")
    assert post().status_code == 200
    smtp.plain.assert_called_once()
    smtp.starttls.assert_called_once()
    smtp.ssl.assert_not_called()


def test_smtp_failure_still_saves_and_never_logs_password(smtp):
    smtp.send_message.side_effect = OSError("connection refused")
    with patch("backend.app.contact.log") as log:
        r = post()
    assert r.status_code == 200 and r.json()["status"] == "received"
    assert rows()[0].email_status == "failed"
    log.warning.assert_called_once()
    assert "s3cret-pass" not in repr(log.method_calls)


def test_not_configured_still_saves(smtp, monkeypatch):
    monkeypatch.delenv("SMTP_HOST")
    assert post().json()["status"] == "received"
    assert rows()[0].email_status == "not_configured"
    smtp.send_message.assert_not_called()


def test_idempotency_replay_saves_and_sends_once(smtp):
    key = uuid4().hex
    assert post(key).status_code == 200 and post(key).status_code == 200
    assert len(rows()) == 1 and smtp.send_message.call_count == 1
    assert client.post("/contact", json=body()).status_code == 422  # key required


def test_honeypot_returns_success_without_saving(smtp):
    r = post(website="http://spam.example")
    assert r.status_code == 200 and r.json()["status"] == "received"
    assert rows() == [] and not smtp.send_message.called


def test_rate_limit_five_per_hour(smtp):
    assert [post().status_code for _ in range(5)] == [200] * 5
    assert post().status_code == 429
    assert len(rows()) == 5


def test_header_injection_is_stripped(smtp):
    r = post(name="Eve\r\nBcc: victim@example.com", email="eve@example.com\r\nBcc: victim@example.com")
    assert r.status_code in (200, 422)
    for row in rows():
        assert "\n" not in row.name + row.email and "\r" not in row.name + row.email
    for call in smtp.send_message.call_args_list:
        msg = call[0][0]
        assert msg["Bcc"] is None and "\n" not in msg["Subject"] and "\n" not in msg["Reply-To"]
    r = post(name="Eve\r\nBcc: victim@example.com", email="eve@example.com")
    assert r.status_code == 200
    msg = smtp.send_message.call_args[0][0]
    assert msg["Bcc"] is None and "\n" not in msg["Subject"]
    assert post(email="not-an-email").status_code == 422


def test_safety_hit_fixed_message_flagged_not_emailed(smtp):
    r = post(message=f"{TAG} I want to kill myself")
    assert r.json() == {"status": "crisis", "message": CRISIS_MESSAGE} and "14416" in r.json()["message"]
    [row] = rows()
    assert row.high_priority and row.email_status == "skipped"
    smtp.send_message.assert_not_called()


def test_message_length_limit(smtp):
    assert post(message=TAG + "x" * 1500).status_code == 422
    assert post(message=(TAG + " ").ljust(1500, "x")).status_code == 200


@pytest.fixture
def people():
    with SessionLocal() as db:
        out = {}
        for role in ("admin", "client", "therapist", "practice_owner"):
            u = User(email=f"{role}-{uuid4().hex[:8]}@example.com", password_hash=hash_password("x" * 12), role=role)
            db.add(u)
            out[role] = u
        db.commit()
        info = {r: ({"Authorization": "Bearer " + create_access_token(u.email, u.role)}, u.id) for r, u in out.items()}
    yield {r: h for r, (h, _) in info.items()}
    with SessionLocal() as db:
        db.execute(delete(User).where(User.id.in_([i for _, i in info.values()])))
        db.commit()


def test_admin_list_is_admin_only(smtp, people):
    post()
    post(message=f"{TAG} I want to kill myself")
    assert client.get("/admin/contact-messages").status_code in (401, 403)
    for role in ("client", "therapist", "practice_owner"):
        assert client.get("/admin/contact-messages", headers=people[role]).status_code == 403
    r = client.get("/admin/contact-messages", headers=people["admin"])
    assert r.status_code == 200
    mine = [m for m in r.json() if m["message"].startswith(TAG)]
    assert len(mine) == 2 and mine[0]["high_priority"] is True
    assert set(mine[0]) == {"id", "name", "email", "message", "high_priority", "email_status", "created_at"}
