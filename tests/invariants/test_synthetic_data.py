"""Invariant: synthetic data only. Seeds, knowledge base and evaluation data may contain only reserved example
addresses and no phone numbers, so real client data cannot enter through fixtures."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = sorted([*ROOT.glob("backend/scripts/seed*.py"), *ROOT.glob("kb/*.md"), ROOT / "backend/app/risk_data.py",
                *ROOT.glob("tests/*.csv"), *ROOT.glob("backend/evals/**/*.json*"), *ROOT.glob("backend/evals/**/*.csv")])
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
RESERVED = re.compile(r"(^|\.)(example\.(com|org|net)|[a-z]+\.(test|invalid|example|localhost))$|^localhost$")
PHONE = re.compile(r"(?<![\w.])(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_only_reserved_emails_and_no_phone_numbers(path: Path) -> None:
    text = path.read_text()
    bad = [m.group(0) for m in EMAIL.finditer(text) if not RESERVED.search(m.group(1).lower())]
    assert not bad, f"non-reserved email addresses in {path.name}: {bad[:5]}"
    phones = PHONE.findall(text)
    assert not phones, f"phone-number-like values in {path.name}"


def test_the_scan_covers_the_seed_and_kb() -> None:
    names = {p.name for p in FILES}
    assert "seed.py" in names and "seed_data.py" in names and any(n.endswith(".md") for n in names)
