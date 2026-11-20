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
    tried = 0
    for m in re.finditer(r"[{\[]", text):
        if tried >= _MAX_STARTS:
            break
        tried += 1
        end = _balanced_end(text, m.start())
        if end is None:
            continue
        try:
            return json.loads(text[m.start():end])
        except json.JSONDecodeError:
            continue
    return None


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
