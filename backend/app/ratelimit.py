"""Per-IP sliding-window rate limits (in-memory, single API process; fine for the demo)."""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    # X-Forwarded-For is only trusted when the API sits behind Caddy alone (TRUST_PROXY=1).
    if os.getenv("TRUST_PROXY") == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, env_var: str, default: int, window_seconds: int = 60):
    def dependency(request: Request) -> None:
        limit = int(os.getenv(env_var, str(default)))
        now = time.monotonic()
        hits = _hits[(bucket, client_ip(request))]
        while hits and now - hits[0] > window_seconds:
            hits.popleft()
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.",
                                headers={"Retry-After": str(window_seconds)})
        hits.append(now)

    return dependency


client_rate_limit = rate_limit("client", "RATE_LIMIT_CLIENT_PER_MIN", 60)
contact_rate_limit = rate_limit("contact", "RATE_LIMIT_CONTACT_PER_MIN", 5)


def reset() -> None:
    _hits.clear()
