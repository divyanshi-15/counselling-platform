from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from backend.app.auth import create_access_token, hash_password
from backend.app.db import SessionLocal
from backend.app.main import app
from backend.app.models import (Practice, TherapistEducation, TherapistLicense, TherapistProfile, User,
                                VerificationDocument)
from backend.scripts import seed as seed_mod

client = TestClient(app)
PDF = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
EDU = {"degree": "M.Phil Clinical Psychology", "institution": "Test Institute", "year": 2015}
LIC = {"license_type": "Clinical Psychologist", "registration_body": "Test Council", "registration_number": "TST-0001",
       "issue_year": 2016, "valid_until": "2030-01-31"}


@pytest.fixture(autouse=True)
def private_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    return tmp_path / "verification"


def _user(db, role: str, tag: str) -> User:
    u = User(email=f"{tag}-{uuid4().hex[:8]}@example.com", password_hash=hash_password("x" * 12), role=role, name=tag.title())
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def world():
    with SessionLocal() as db:
        owner, admin, cl = _user(db, "practice_owner", "owner"), _user(db, "admin", "admin"), _user(db, "client", "client")
        practice = Practice(name="Verif Practice", slug=uuid4().hex, owner_id=owner.id, status="published", verified=True, page_json="{}")
        db.add(practice)
        db.flush()
        users, profiles = {"owner": owner, "admin": admin, "client": cl}, {}
        for tag in ("a", "b"):
            t = _user(db, "therapist", f"therapist-{tag}")
            users[tag] = t
            p = TherapistProfile(user_id=t.id, practice_id=practice.id, bio="", approaches=[], languages=["en"], fee=1000, verified=False)
            db.add(p)
            db.flush()
            profiles[tag] = p.id
        db.commit()
        emails = {k: (u.email, u.role) for k, u in users.items()}
        ids = [u.id for u in users.values()]
        practice_id = practice.id
    heads = {k: {"Authorization": f"Bearer {create_access_token(e, r)}"} for k, (e, r) in emails.items()}
    yield {"h": heads, "p": profiles, "practice_id": practice_id}
    with SessionLocal() as db:
        db.execute(delete(VerificationDocument).where(VerificationDocument.owner_id.in_(profiles.values())))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.execute(delete(Practice).where(Practice.id == practice_id))
        db.commit()


def _upload(w, who="a", content=PDF, name="cert.pdf", doc_type="degree_certificate", ctype="application/pdf"):
    return client.post("/therapists/me/documents", headers=w["h"][who], data={"doc_type": doc_type},
                       files={"file": (name, content, ctype)})


def _complete(w, who="a") -> int:
    assert client.post("/therapists/me/education", headers=w["h"][who], json=EDU).status_code == 201
    assert client.post("/therapists/me/licenses", headers=w["h"][who], json=LIC).status_code == 201
    r = _upload(w, who)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _status(w, who="a") -> str:
    return client.get("/therapists/me/verification", headers=w["h"][who]).json()["status"]


def _review(w, pid, decision, note=None):
    return client.post(f"/admin/therapists/{pid}/review", headers=w["h"]["admin"], json={"decision": decision, "note": note})


# ---------- profile ----------

def test_therapist_edits_own_profile_only(world) -> None:
    body = {"bio": "Warm, practical.", "languages": ["en", "hi"], "specialisations": ["sleep", "stress"], "fee": 1700, "years_experience": 9}
    r = client.patch("/therapists/me/profile", headers=world["h"]["a"], json=body)
    assert r.status_code == 200 and r.json()["fee"] == 1700 and r.json()["languages"] == ["en", "hi"]
    assert r.json()["verification_status"] == "draft"
    other = client.get("/therapists/me/profile", headers=world["h"]["b"]).json()
    assert other["fee"] == 1000 and other["bio"] == ""


@pytest.mark.parametrize("body", [{"languages": ["kn"]}, {"languages": []}, {"fee": 0}, {"verified": True},
                                  {"verification_status": "verified"}, {"years_experience": -1}, {"fee": None}])
def test_profile_edit_rejects_bad_input_and_privilege_fields(world, body) -> None:
    assert client.patch("/therapists/me/profile", headers=world["h"]["a"], json=body).status_code == 422


@pytest.mark.parametrize("who", ["client", "owner", "admin"])
def test_non_therapists_cannot_use_therapist_endpoints(world, who) -> None:
    h = world["h"][who]
    assert client.patch("/therapists/me/profile", headers=h, json={"fee": 5}).status_code == 403
    assert client.post("/therapists/me/education", headers=h, json=EDU).status_code == 403
    assert client.post("/therapists/me/licenses", headers=h, json=LIC).status_code == 403
    assert client.get("/therapists/me/verification", headers=h).status_code == 403
    assert client.post("/therapists/me/documents", headers=h, data={"doc_type": "other"},
                       files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 403
    assert client.post("/therapists/me/verification/submit", headers=h).status_code == 403


def test_unauthenticated_requests_are_rejected(world) -> None:
    assert client.get("/therapists/me/verification").status_code == 401
    assert client.get("/verification-documents/1/download").status_code == 401


# ---------- education and licenses ----------

def test_education_and_license_crud_are_owner_scoped(world) -> None:
    ha, hb = world["h"]["a"], world["h"]["b"]
    edu = client.post("/therapists/me/education", headers=ha, json=EDU).json()
    lic = client.post("/therapists/me/licenses", headers=ha, json=LIC).json()
    assert client.put(f"/therapists/me/education/{edu['id']}", headers=ha, json=EDU | {"year": 2016}).json()["year"] == 2016
    assert client.put(f"/therapists/me/licenses/{lic['id']}", headers=ha, json=LIC | {"valid_until": None}).json()["valid_until"] is None
    for path, body in ((f"education/{edu['id']}", EDU), (f"licenses/{lic['id']}", LIC)):  # cross-therapist
        assert client.put(f"/therapists/me/{path}", headers=hb, json=body).status_code == 404
        assert client.delete(f"/therapists/me/{path}", headers=hb).status_code == 404
    assert client.delete(f"/therapists/me/education/{edu['id']}", headers=ha).status_code == 204
    assert client.delete(f"/therapists/me/licenses/{lic['id']}", headers=ha).status_code == 204
    assert client.get("/therapists/me/verification", headers=hb).json()["education"] == []


@pytest.mark.parametrize("path,body", [("education", EDU | {"year": 1800}), ("education", EDU | {"year": 2999}),
                                       ("education", EDU | {"degree": ""}), ("licenses", LIC | {"issue_year": 2999}),
                                       ("licenses", LIC | {"valid_until": "2010-01-01"}), ("licenses", LIC | {"extra": 1})])
def test_credential_validation(world, path, body) -> None:
    assert client.post(f"/therapists/me/{path}", headers=world["h"]["a"], json=body).status_code == 422


# ---------- documents ----------

def test_upload_accepts_pdf_jpg_png_validated_by_content(world, private_uploads) -> None:
    for content, name in ((PDF, "a.pdf"), (JPG, "b.jpg"), (JPG, "b2.JPEG"), (PNG, "c.png")):
        r = _upload(world, content=content, name=name, ctype="application/octet-stream")
        assert r.status_code == 201, (name, r.text)
    types = [d["content_type"] for d in client.get("/therapists/me/verification", headers=world["h"]["a"]).json()["documents"]]
    assert types == ["application/pdf", "image/jpeg", "image/jpeg", "image/png"]


@pytest.mark.parametrize("content,name,ctype", [
    (b"just text", "notes.pdf", "application/pdf"),                  # extension lies
    (b"MZ\x90\x00" + b"\x00" * 64, "tool.pdf", "application/pdf"),   # executable renamed
    (PNG, "image.pdf", "application/pdf"),                            # real content, wrong extension
    (PDF, "doc.exe", "application/pdf"),                              # right content, bad extension
    (PDF, "doc", "application/pdf"),
    (b"<html><script>1</script></html>", "x.png", "image/png"),
])
def test_upload_rejects_wrong_content_or_extension(world, content, name, ctype) -> None:
    assert _upload(world, content=content, name=name, ctype=ctype).status_code == 415


def test_upload_rejects_oversize_empty_and_unknown_type(world) -> None:
    assert _upload(world, content=PDF + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert _upload(world, content=PDF + b"0" * (5 * 1024 * 1024 - len(PDF))).status_code == 201  # exactly 5 MB
    assert _upload(world, content=b"").status_code == 422
    assert _upload(world, doc_type="selfie").status_code == 422


def test_files_stored_under_random_private_keys(world, private_uploads) -> None:
    doc = _upload(world, name="../../etc/passwd.pdf").json()
    assert "/" not in doc["filename"] and ".." not in doc["filename"]
    with SessionLocal() as db:
        key = db.scalar(select(VerificationDocument.storage_key).where(VerificationDocument.id == doc["id"]))
    assert len(key) == 32 and key != doc["filename"]
    assert (private_uploads / key).read_bytes() == PDF
    assert oct((private_uploads / key).stat().st_mode & 0o777) == "0o600"
    # no public route serves the storage directory
    for path in (f"/uploads/{key}", f"/verification/{key}", f"/static/{key}", f"/documents/{doc['id']}"):
        assert client.get(path).status_code in (401, 404)


def test_download_allowed_for_owner_and_admin_only(world) -> None:
    doc_id = _upload(world).json()["id"]
    url = f"/verification-documents/{doc_id}/download"
    for who in ("a", "admin"):
        r = client.get(url, headers=world["h"][who])
        assert r.status_code == 200 and r.content == PDF
        assert r.headers["x-content-type-options"] == "nosniff" and "attachment" in r.headers["content-disposition"]
        assert "no-store" in r.headers["cache-control"]
    assert client.get(url, headers=world["h"]["b"]).status_code == 404       # other therapist
    assert client.get(url, headers=world["h"]["client"]).status_code == 403
    assert client.get(url, headers=world["h"]["owner"]).status_code == 403
    assert client.get("/verification-documents/999999/download", headers=world["h"]["admin"]).status_code == 404


def test_other_therapist_cannot_delete_or_see_documents(world) -> None:
    doc_id = _upload(world).json()["id"]
    assert client.delete(f"/therapists/me/documents/{doc_id}", headers=world["h"]["b"]).status_code == 404
    assert client.get("/therapists/me/verification", headers=world["h"]["b"]).json()["documents"] == []


def test_owner_deletes_document_and_file_is_removed(world, private_uploads) -> None:
    doc_id = _upload(world).json()["id"]
    assert len(list(private_uploads.iterdir())) == 1
    assert client.delete(f"/therapists/me/documents/{doc_id}", headers=world["h"]["a"]).status_code == 204
    assert list(private_uploads.iterdir()) == []


def test_document_count_is_capped(world) -> None:
    for _ in range(10):
        assert _upload(world).status_code == 201
    assert _upload(world).status_code == 409


# ---------- submit and transitions ----------

def test_submit_requires_education_license_and_document(world) -> None:
    h = world["h"]["a"]
    r = client.post("/therapists/me/verification/submit", headers=h)
    assert r.status_code == 422 and "education" in r.json()["detail"] and "license" in r.json()["detail"] and "document" in r.json()["detail"]
    client.post("/therapists/me/education", headers=h, json=EDU)
    client.post("/therapists/me/licenses", headers=h, json=LIC)
    r = client.post("/therapists/me/verification/submit", headers=h)
    assert r.status_code == 422 and r.json()["detail"].endswith("missing document")
    assert _status(world) == "draft"
    _upload(world)
    r = client.post("/therapists/me/verification/submit", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "submitted" and r.json()["submitted_at"]
    assert r.json()["missing"] == []


def test_submitted_profile_is_locked(world) -> None:
    doc_id = _complete(world)
    h = world["h"]["a"]
    client.post("/therapists/me/verification/submit", headers=h)
    assert client.post("/therapists/me/verification/submit", headers=h).status_code == 409
    assert _upload(world).status_code == 409
    assert client.delete(f"/therapists/me/documents/{doc_id}", headers=h).status_code == 409
    assert client.post("/therapists/me/licenses", headers=h, json=LIC).status_code == 409
    assert client.post("/therapists/me/education", headers=h, json=EDU).status_code == 409
    assert client.patch("/therapists/me/profile", headers=h, json={"bio": "Still editable."}).status_code == 200


def test_review_flow_changes_requested_then_verified(world) -> None:
    pid, h = world["p"]["a"], world["h"]["a"]
    assert _review(world, pid, "verified").status_code == 409                       # draft cannot be reviewed
    _complete(world)
    client.post("/therapists/me/verification/submit", headers=h)
    assert _review(world, pid, "changes_requested").status_code == 422             # note required
    assert client.post(f"/admin/therapists/{pid}/review", headers=h, json={"decision": "verified"}).status_code == 403
    r = _review(world, pid, "changes_requested", "Please upload a clearer registration certificate.")
    assert r.status_code == 200 and r.json()["status"] == "changes_requested" and r.json()["verified"] is False
    v = client.get("/therapists/me/verification", headers=h).json()
    assert v["status"] == "changes_requested" and v["reviewer_note"].startswith("Please upload") and v["reviewed_at"]
    assert v["can_edit_documents"] is True
    assert _upload(world, name="clearer.pdf", doc_type="registration_certificate").status_code == 201
    assert client.post("/therapists/me/verification/submit", headers=h).json()["status"] == "submitted"
    r = _review(world, pid, "verified")
    assert r.json()["status"] == "verified" and r.json()["verified"] is True
    assert _review(world, pid, "rejected", "late").status_code == 409              # only submitted can be reviewed


def test_rejected_profile_cannot_resubmit_or_edit_credentials(world) -> None:
    pid, h = world["p"]["a"], world["h"]["a"]
    _complete(world)
    client.post("/therapists/me/verification/submit", headers=h)
    assert _review(world, pid, "rejected", "Registration could not be confirmed.").json()["status"] == "rejected"
    assert client.post("/therapists/me/verification/submit", headers=h).status_code == 409
    assert client.post("/therapists/me/licenses", headers=h, json=LIC).status_code == 409
    with SessionLocal() as db:
        assert db.get(TherapistProfile, pid).verified is False


def test_public_listing_needs_verified_and_never_shows_license_numbers(world) -> None:
    pid, h = world["p"]["a"], world["h"]["a"]
    _complete(world)
    ids = lambda: [t["id"] for t in client.get("/therapists/public").json()["items"]]  # noqa: E731
    assert pid not in ids()
    client.post("/therapists/me/verification/submit", headers=h)
    assert pid not in ids()
    _review(world, pid, "verified")
    assert pid in ids()
    for text in (client.get("/therapists/public").text, client.get(f"/therapists/public/{pid}").text):
        assert "TST-0001" not in text and "registration_number" not in text and "storage_key" not in text
    # a client or owner cannot read credentials through the therapist's own endpoints either
    assert client.get("/therapists/me/verification", headers=world["h"]["client"]).status_code == 403


def test_verified_therapist_editing_license_returns_to_review(world) -> None:
    pid, h = world["p"]["a"], world["h"]["a"]
    _complete(world)
    client.post("/therapists/me/verification/submit", headers=h)
    _review(world, pid, "verified")
    lic = client.get("/therapists/me/verification", headers=h).json()["licenses"][0]
    # profile and education edits keep the badge
    assert client.patch("/therapists/me/profile", headers=h, json={"bio": "Updated bio."}).json()["verified"] is True
    assert client.put(f"/therapists/me/education/{client.get('/therapists/me/verification', headers=h).json()['education'][0]['id']}",
                      headers=h, json=EDU | {"year": 2014}).status_code == 200
    assert _status(world) == "verified"
    assert client.put(f"/therapists/me/licenses/{lic['id']}", headers=h, json=LIC | {"registration_number": "TST-0002"}).status_code == 200
    v = client.get("/therapists/me/verification", headers=h).json()
    assert v["status"] == "submitted"
    assert pid not in [t["id"] for t in client.get("/therapists/public").json()["items"]]
    # the last license cannot be removed once past draft
    assert client.delete(f"/therapists/me/licenses/{lic['id']}", headers=h).status_code in (409,)


def test_admin_queue_lists_submitted_therapists_with_completeness(world) -> None:
    pid = world["p"]["a"]
    admin = world["h"]["admin"]
    q = lambda **p: client.get("/admin/verification-queue", headers=admin, params=p).json()["items"]
    assert pid not in [i["id"] for i in q()]
    _complete(world)
    client.post("/therapists/me/verification/submit", headers=world["h"]["a"])
    item = next(i for i in q() if i["id"] == pid)
    assert item["name"] == "Therapist-A" and item["submitted_at"] and item["verification_status"] == "submitted"
    assert {c["label"]: c["count"] for c in item["completeness"]} == {"Education": 1, "Licences": 1, "Documents": 1}
    assert _review(world, pid, "rejected", "Registration number does not match.").status_code == 200
    assert pid not in [i["id"] for i in q()] and pid in [i["id"] for i in q(status="rejected")]


@pytest.mark.parametrize("who", ["a", "client", "owner"])
def test_therapist_audit_and_queue_are_admin_only(world, who) -> None:
    assert client.get("/admin/verification-queue", headers=world["h"][who]).status_code == 403
    assert client.get(f"/admin/therapists/{world['p']['a']}/audit", headers=world["h"][who]).status_code == 403


def test_therapist_review_is_audited_with_note_and_idempotent(world) -> None:
    pid = world["p"]["a"]
    _complete(world)
    client.post("/therapists/me/verification/submit", headers=world["h"]["a"])
    assert _review(world, pid, "changes_requested").status_code == 422
    assert _review(world, pid, "rejected", "   ").status_code == 422
    assert _review(world, pid, "changes_requested", "Upload a clearer licence scan.").status_code == 200
    assert _review(world, pid, "changes_requested", "Upload a clearer licence scan.").status_code == 200
    assert _review(world, pid, "verified").status_code == 409  # no longer submitted
    client.post("/therapists/me/verification/submit", headers=world["h"]["a"])
    assert _review(world, pid, "verified").status_code == 200
    assert _review(world, pid, "verified").status_code == 200
    assert _review(world, pid, "rejected", "Changed my mind.").status_code == 409
    hist = client.get(f"/admin/therapists/{pid}/audit", headers=world["h"]["admin"]).json()["items"]
    reviews = [i for i in hist if i["action"] == "therapist.review"]
    assert [(r["decision"], r["note"]) for r in reviews] == [("verified", None), ("changes_requested", "Upload a clearer licence scan.")]
    assert reviews[0]["actor_role"] == "admin"
    assert client.get("/admin/therapists/999999/audit", headers=world["h"]["admin"]).status_code == 404


def test_legacy_therapist_verify_toggle_is_gone(world) -> None:
    assert client.post(f"/admin/therapists/{world['p']['a']}/verify", headers=world["h"]["admin"], json={"verified": True}).status_code in (404, 405)


def test_admin_review_detail_is_admin_only(world) -> None:
    pid = world["p"]["a"]
    _complete(world)
    r = client.get(f"/admin/therapists/{pid}/verification", headers=world["h"]["admin"])
    assert r.status_code == 200 and r.json()["licenses"][0]["registration_number"] == "TST-0001"
    for who in ("a", "b", "client", "owner"):
        assert client.get(f"/admin/therapists/{pid}/verification", headers=world["h"][who]).status_code == 403
        assert client.post(f"/admin/therapists/{pid}/review", headers=world["h"][who], json={"decision": "verified"}).status_code == 403


# ---------- seed ----------

def test_seed_credentials_and_pending_therapist(private_uploads) -> None:
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(User).where(User.email.in_([row[0] for row in seed_mod.LOGINS])))
            db.execute(delete(Practice).where(Practice.slug.in_(seed_mod.PRACTICE_SLUGS)))
            db.commit()
    wipe()
    now = datetime(2030, 3, 4, 8, 0, tzinfo=timezone.utc)
    try:
        with SessionLocal() as db:
            seed_mod.seed(db, load_kb=False, now=now)
            counts = [db.scalar(select(func.count()).select_from(m)) for m in (TherapistEducation, TherapistLicense, VerificationDocument)]
            seed_mod.seed(db, load_kb=False, now=now)  # idempotent
            assert counts == [db.scalar(select(func.count()).select_from(m)) for m in (TherapistEducation, TherapistLicense, VerificationDocument)]
            profiles = {u.email: p for p, u in db.execute(select(TherapistProfile, User).join(User, User.id == TherapistProfile.user_id)).all()
                        if u.email in {row[0] for row in seed_mod.LOGINS}}
            pending = profiles["therapist10@example.com"]
            assert (pending.verification_status, pending.verified) == ("submitted", False)
            assert pending.submitted_at is not None
            verified = [p for e, p in profiles.items() if e != "therapist10@example.com"]
            assert len(verified) == 9 and all(p.verification_status == "verified" and p.verified for p in verified)
            for p in profiles.values():
                assert db.scalar(select(func.count()).select_from(TherapistEducation).where(TherapistEducation.therapist_id == p.id)) >= 1
                assert db.scalar(select(func.count()).select_from(TherapistLicense).where(TherapistLicense.therapist_id == p.id)) == 1
                assert db.scalar(select(func.count()).select_from(VerificationDocument).where(VerificationDocument.owner_id == p.id)) == 2
            pending_id = pending.id
            admin = db.scalar(select(User).where(User.email == "admin@example.com"))
            doc_id = db.scalar(select(VerificationDocument.id).where(VerificationDocument.owner_id == pending_id))
            h = {"Authorization": f"Bearer {create_access_token(admin.email, admin.role)}"}
        assert pending_id not in [t["id"] for t in client.get("/therapists/public").json()["items"]]
        assert client.get(f"/verification-documents/{doc_id}/download", headers=h).content.startswith(b"%PDF-")
        assert _review_seed(pending_id, h).json()["status"] == "verified"
    finally:
        wipe()


def _review_seed(pid, h):
    return client.post(f"/admin/therapists/{pid}/review", headers=h, json={"decision": "verified"})
