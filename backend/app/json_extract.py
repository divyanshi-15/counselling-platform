"""Tolerant JSON extraction from model text: code fences, leading prose, trailing chatter."""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*\n?(.*?)```", re.S)
_MAX_STARTS = 20


def _balanced_end(text: str, start: int) -> int | None:
    """Index just past the object/array that opens at `start`, honouring strings and escapes; None if it never closes."""
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:
                return i + 1
    return None


def _scan(text: str) -> Any | None:
    """First complete JSON value. A structure that never closes (truncated reply) ends the scan: anything after
    its opening brace is a fragment of it, and returning a nested piece would hand back the wrong shape."""
    pos, tried = 0, 0
    while tried < _MAX_STARTS and (m := re.compile(r"[{\[]").search(text, pos)):
        tried += 1
        end = _balanced_end(text, m.start())
        if end is None:
            return None
        try:
            return json.loads(text[m.start():end])
        except json.JSONDecodeError:
            pos = end
    return None


class ModelText(str):
    """Model reply text that remembers why generation stopped (e.g. 'max_tokens' = truncated)."""
    stop_reason: str | None = None

    def __new__(cls, text: str, stop_reason: str | None = None) -> "ModelText":
        obj = super().__new__(cls, text)
        obj.stop_reason = stop_reason
        return obj


def was_truncated(raw: Any) -> bool:
    return getattr(raw, "stop_reason", None) == "max_tokens"


def extract_json(text: str | None) -> Any | None:
    """First parseable JSON object/array in `text`, or None. Fenced blocks are tried before the raw text."""
    if not text or not text.strip():
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    for block in _FENCE_RE.findall(text):
        if (found := _scan(block)) is not None:
            return found
    return _scan(text)
