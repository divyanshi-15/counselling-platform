"""Real models wrap JSON in fences, add a sentence, or get cut off by max_tokens. Mocked replies for the three agents."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from test_braindump import GOOD as DUMP
from test_braindump import TEXT, _actions, _post
from test_copilot import GOOD as BRIEF  # noqa: F401  (world is a fixture)
from test_copilot import FakeModel, _h, _setup_case, world

from backend.app.agents import copilot, monitor
from backend.app.agents.copilot import RetryBlock, ask_json, call_model
from backend.app.json_extract import ModelText, extract_json

PLAN = {"update_text": "Scores have held steady, so consider whether the evening goals still fit."}
FENCED = lambda d: "```json\n" + json.dumps(d) + "\n```"  # noqa: E731
SENTENCE = lambda d: "Here is the JSON you asked for: " + json.dumps(d) + " Let me know if you need changes."  # noqa: E731
CUT = lambda d: ModelText(json.dumps(d)[: len(json.dumps(d)) // 2], "max_tokens")  # noqa: E731
PROSE = ["I would suggest focusing on sleep and worry.", "Sorry, in plain words: focus on sleep."]


class Recorder:
    """Scripted model that also records max_tokens and the blocks of every call."""

    def __init__(self, replies):
        self.replies, self.limits, self.blocks = list(replies), [], []

    def __call__(self, system, blocks, *, max_tokens):
        self.limits.append(max_tokens)
        self.blocks.append(blocks)
        if "Structure these session notes" in blocks[0][0]:
            return json.dumps({"themes": ["sleep"], "client_reported": ["lies awake"], "homework": None})
        item = self.replies.pop(0)
        return item if isinstance(item, str) else json.dumps(item)


def _briefing(client, w):
    return client.post("/therapists/me/prepare-my-day", headers=_h(w["ta"])).json()["items"][0]


# ---------- copilot briefing ----------

@pytest.mark.parametrize("wrap", [FENCED, SENTENCE])
def test_briefing_accepts_fenced_or_prefixed_json(world, monkeypatch, wrap) -> None:
    client, w = world
    _setup_case(client, w)
    model = FakeModel([wrap(BRIEF)])
    monkeypatch.setattr(copilot, "call_model", model)
    assert _briefing(client, w)["status"] == "ok" and model.briefing_calls == 1


def test_briefing_truncated_reply_retries_with_more_room_and_the_previous_reply(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    cut = CUT(BRIEF)
    model = Recorder([cut, BRIEF])
    monkeypatch.setattr(copilot, "call_model", model)
    assert _briefing(client, w)["status"] == "ok"
    draft_limits = model.limits[-2:]
    assert draft_limits[1] == draft_limits[0] * 2
    retry = model.blocks[-1][-1]
    assert isinstance(retry, RetryBlock) and retry.previous == str(cut).strip() and "cut off" in retry.text
    assert retry.text.endswith("Reply with ONLY the JSON object, no prose, no code fences.")


def test_briefing_prose_only_fails_visibly_after_one_retry(world, monkeypatch) -> None:
    client, w = world
    _setup_case(client, w)
    model = Recorder(PROSE)
    monkeypatch.setattr(copilot, "call_model", model)
    item = _briefing(client, w)
    assert item["status"] == "error" and item["pending_action_id"] is None and "no JSON object" in item["error"]
    assert len(model.blocks) == 3  # structure_notes + exactly two drafts


# ---------- brain dump ----------

@pytest.mark.parametrize("wrap", [FENCED, SENTENCE])
def test_brain_dump_accepts_fenced_or_prefixed_json(world, monkeypatch, wrap) -> None:
    client, w = world
    model = Recorder([wrap(DUMP)])
    monkeypatch.setattr(copilot, "call_model", model)
    assert _post(client, w["ca"]).json()["status"] == "shared" and len(model.blocks) == 1
    assert _actions(w["ca"].id)[0].payload["draft"]["themes"] == DUMP["themes"]


def test_brain_dump_truncated_reply_then_success(world, monkeypatch) -> None:
    client, w = world
    cut = CUT(DUMP)
    model = Recorder([cut, DUMP])
    monkeypatch.setattr(copilot, "call_model", model)
    assert _post(client, w["ca"]).json()["status"] == "shared"
    assert model.limits[1] == model.limits[0] * 2 and model.blocks[1][-1].previous == str(cut)
    assert _actions(w["ca"].id)[0].payload["draft"]["summary"] == DUMP["summary"]


def test_brain_dump_prose_only_fails_visibly_but_keeps_the_note(world, monkeypatch) -> None:
    client, w = world
    model = Recorder(PROSE)
    monkeypatch.setattr(copilot, "call_model", model)
    assert _post(client, w["ca"]).json()["status"] == "error" and len(model.blocks) == 2
    (action,) = _actions(w["ca"].id)
    assert action.payload["draft"] is None and action.payload["text"] == TEXT


# ---------- plan update (monitor) ----------

def _plan_text(monkeypatch, replies):
    model = Recorder(replies)
    monkeypatch.setattr(monitor, "call_model", model)
    plan = SimpleNamespace(goals_json=[{"text": "Sleep better"}])
    return model, monitor.draft_update_text(plan, {"plateau": []}, safe_for_model=True)


@pytest.mark.parametrize("wrap", [FENCED, SENTENCE])
def test_plan_update_accepts_fenced_or_prefixed_json(monkeypatch, wrap) -> None:
    model, (text, status) = _plan_text(monkeypatch, [wrap(PLAN)])
    assert (text, status) == (PLAN["update_text"], "ok") and len(model.blocks) == 1


def test_plan_update_truncated_reply_then_success(monkeypatch) -> None:
    cut = CUT(PLAN)
    model, (text, status) = _plan_text(monkeypatch, [cut, PLAN])
    assert (text, status) == (PLAN["update_text"], "ok")
    assert model.limits[1] == model.limits[0] * 2 and model.blocks[1][-1].previous == str(cut)


def test_plan_update_prose_only_gives_visible_error_and_manual_text(monkeypatch) -> None:
    model, (text, status) = _plan_text(monkeypatch, PROSE)
    assert status.startswith("error: draft rejected after one retry") and "please edit" in text and len(model.blocks) == 2


# ---------- shared helpers ----------

def test_truncated_reply_never_yields_a_nested_fragment() -> None:
    cut = '{"summary": "s", "suggestions": [{"text": "a", "chunk_ids": [1]}, {"text": "b", "chunk_ids'
    assert extract_json(cut) is None  # the complete inner object must not be returned as if it were the reply


def test_ask_json_unavailable_and_limit_cap() -> None:
    assert ask_json("s", [("p", False)], max_tokens=10, build=lambda p: p, call=lambda *a, **k: None) == ("unavailable", None)
    limits = []

    def always_cut(system, blocks, *, max_tokens):
        limits.append(max_tokens)
        return ModelText("{", "max_tokens")

    assert ask_json("s", [("p", False)], max_tokens=3000, build=lambda p: p, call=always_cut)[0] == "error"
    assert limits == [3000, 4000]


def test_call_model_disables_thinking_replays_the_previous_reply_and_skips_caching_truncated(monkeypatch) -> None:
    monkeypatch.setenv("FAKE_LLM", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(copilot, "_budget_exceeded", lambda: False)
    monkeypatch.setattr(copilot, "_cached_model_output", lambda *a: None)
    written = []
    monkeypatch.setattr(copilot, "_write_cache", lambda *a: written.append(a))
    resp = MagicMock()
    resp.json.return_value = {"content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": '{"a": 1'}],
                              "stop_reason": "max_tokens", "usage": {"input_tokens": 5, "output_tokens": 7}}
    with patch.object(copilot.httpx, "post", return_value=resp) as post:
        out = call_model("sys", copilot.retry_blocks([("question", True)], "prev reply", "bad"), max_tokens=50)
    body = post.call_args.kwargs["json"]
    assert body["thinking"] == {"type": "disabled"} and body["max_tokens"] == 50
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
    assert body["messages"][1]["content"] == "prev reply" and "not valid JSON for this schema: bad" in body["messages"][2]["content"]
    assert out.stop_reason == "max_tokens" and str(out) == '{"a": 1' and written == []
