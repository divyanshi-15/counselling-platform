from types import SimpleNamespace

from app.auth import can_access_client_data, can_access_practice_owner_data, can_access_therapist_data


def test_client_access_is_self_only() -> None:
    client = SimpleNamespace(id=10, role="client")
    assert can_access_client_data(client, 10) is True
    assert can_access_client_data(client, 11) is False


def test_cross_client_cannot_read_other_client_data() -> None:
    alice = SimpleNamespace(id=10, role="client")
    bob = SimpleNamespace(id=11, role="client")
    assert can_access_client_data(alice, bob.id) is False
    assert can_access_client_data(bob, alice.id) is False


def test_therapist_access_is_self_only() -> None:
    therapist = SimpleNamespace(id=22, role="therapist")
    assert can_access_therapist_data(therapist, 22) is True
    assert can_access_therapist_data(therapist, 23) is False


def test_cross_therapist_cannot_read_other_therapist_data() -> None:
    a = SimpleNamespace(id=22, role="therapist")
    b = SimpleNamespace(id=23, role="therapist")
    assert can_access_therapist_data(a, b.id) is False
    assert can_access_therapist_data(b, a.id) is False


def test_practice_owner_access_is_self_only() -> None:
    owner = SimpleNamespace(id=51, role="practice_owner")
    assert can_access_practice_owner_data(owner, 51) is True
    assert can_access_practice_owner_data(owner, 52) is False


def test_practice_owner_cannot_access_clinical_data() -> None:
    owner = SimpleNamespace(id=51, role="practice_owner")
    assert can_access_practice_owner_data(owner, 52) is False
    assert can_access_practice_owner_data(owner, 51) is True


def test_admin_can_access_all() -> None:
    admin = SimpleNamespace(id=99, role="admin")
    assert can_access_client_data(admin, 5) is True
    assert can_access_therapist_data(admin, 7) is True
    assert can_access_practice_owner_data(admin, 9) is True
