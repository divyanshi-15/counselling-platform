"""FAKE_LLM=1: every model call returns a deterministic canned output (e2e and offline demos). No network, no cache."""
from __future__ import annotations

import json
import os
import re
from typing import Any


class FakeLLMConfigError(RuntimeError):
    pass


def enabled() -> bool:
    return os.getenv("FAKE_LLM", "0") == "1"


def assert_safe_config() -> None:
    """Refuse to start a production deployment that would serve canned 'AI' output to real users."""
    if enabled() and os.getenv("DEMO_MODE", "0") != "1" and os.getenv("APP_ENV", "development") == "production":
        raise FakeLLMConfigError("FAKE_LLM=1 is not allowed when APP_ENV=production and DEMO_MODE=0")


def complete(system: str, text: str) -> str:
    """Canned text for the model call identified by its system prompt / prompt text."""
    if system.startswith("You draft the public web page text"):
        data = json.loads(re.search(r"<<<PRACTICE_DATA>>>\n(.*?)\n<<<END_PRACTICE_DATA>>>", text, re.S).group(1))
        topics = ", ".join(data.get("specialisations") or ["everyday wellbeing"])
        return json.dumps({
            "tagline": f"Unhurried, practical counselling in {data.get('city', 'your city')}.",
            "about": f"{data.get('name', 'This practice')} offers collaborative, skill-building sessions for {topics}.\n\n"
                     f"Our approach: {data.get('approach', 'a warm, structured style')}. "
                     "Between sessions you get small, clear next steps.\n\n- Warm, paced support\n- Clear goals you set together"})
    if system.startswith("You draft practice web pages"):
        owner = re.search(r"<owner-data>(.*?)</owner-data>", text, re.S)
        data: dict[str, Any] = json.loads(owner.group(1)) if owner else {}
        name, where = data.get("name", "This practice"), data.get("location", "your city")
        return json.dumps({
            "tagline": f"Calm, practical support in {where} (fictional demo).",
            "about": f"{name} offers collaborative, skill-building support with clear next steps.",
            "services": [{"title": "Initial consultation", "description": "A first conversation about your goals."},
                         {"title": "Ongoing support", "description": "Paced, structured sessions."}],
            "faq": [{"question": "What should I expect?", "answer": "Warm, clear, step-by-step support."}],
            "what_to_expect": ["A collaborative plan", "Simple next steps between sessions"],
        })
    if system.startswith("You turn a client's private note"):
        return json.dumps({"themes": ["worry about the week ahead", "difficulty switching off"],
                           "mood_tags": ["anxious", "tired"], "exercise_kb_slug": "worry-postponement",
                           "summary": "The client describes ongoing worry that is hard to put down. "
                                      "A short worry-postponement exercise may fit; please review."})
    if system.startswith("Check whether practice copy"):
        return json.dumps({"passed": True, "reasons": []})
    if system.startswith("You help a licensed therapist revise"):
        return json.dumps({"update_text": "Scores have held steady over the last two weeks, so consider whether the "
                                          "bedtime goal and the between-session exercises still fit; please confirm "
                                          "with the client before changing the plan."})
    if text.startswith("Structure these session notes"):
        return json.dumps({"themes": ["racing thoughts at night", "low energy during the day"],
                           "client_reported": ["takes a long time to fall asleep"], "homework": None})
    marker = "RETRIEVED knowledge entries (cite only these chunk_ids):\n"
    if marker in text:
        chunks = json.loads(text.split(marker, 1)[1].split("\n", 1)[0])
        ids = [c["chunk_id"] for c in chunks]
        return json.dumps({
            "summary": "The notes point toward evening worry keeping bedtime late; please confirm.",
            "suggestions": [{"text": "Consider a short between-session exercise that matches the evening themes; "
                                     "please confirm it fits the plan.", "chunk_ids": ids, "note_quotes": []}] if ids else [],
        })
    raise FakeLLMConfigError("FAKE_LLM has no canned output for this prompt")
