"""Invariant: the deterministic post-check runs on all AI output. Any backend module that calls the model must also
reference a post-check, so a new agent cannot be added without one. Behavioural proof per agent is in
test_ai_proposes.py and the agent-specific suites (test_copilot, test_monitor, test_practice_launch_agent)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "backend" / "app"
MODEL_CALL = re.compile(r"\b(call_model|ask_json|_call_anthropic)\(|httpx\.post\(")
POST_CHECKS = ("clinical_output_violations", "launch_violations", "check_claims", "validate_ai_output")

CALLERS = sorted(p for p in APP.rglob("*.py") if MODEL_CALL.search(p.read_text()))


def test_the_scan_finds_the_known_agents() -> None:
    names = {p.name for p in CALLERS}
    assert {"copilot.py", "monitor.py", "launch.py", "braindump.py", "journeys.py"} <= names


@pytest.mark.parametrize("path", CALLERS, ids=lambda p: p.name)
def test_module_that_calls_a_model_has_a_post_check(path: Path) -> None:
    source = path.read_text()
    assert any(check in source for check in POST_CHECKS), (
        f"{path.relative_to(APP.parent.parent)} calls a model but references none of {POST_CHECKS}")
