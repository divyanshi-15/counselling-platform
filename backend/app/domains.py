"""Domain availability and DNS adapter. GoDaddy today; swap by changing `get_provider`.

Read-only by default: availability checks never buy anything, and there is no purchase method at all. DNS writes exist
only behind `dns_write_enabled()` (GODADDY_ALLOW_DNS_WRITE=1) and are called only from an owner-triggered endpoint.
Missing credentials or a 401/403 give status "unknown" with a reason; nothing is ever invented.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+(com|in|co\.in|org|care|health)$")
TIMEOUT = 10.0


@dataclass(frozen=True)
class DomainCheck:
    domain: str
    status: str  # available | taken | unknown
    price: float | None = None
    currency: str | None = None
    reason: str | None = None  # why availability is unknown


@dataclass(frozen=True)
class DnsRecord:
    type: str  # A | CNAME
    name: str  # "@" or "www"
    data: str
    ttl: int = 600


class DnsWriteError(Exception):
    pass


class DomainProvider(Protocol):
    def check(self, domain: str) -> DomainCheck: ...
    def apply_records(self, domain: str, records: list[DnsRecord]) -> None: ...


def dns_write_enabled() -> bool:
    return os.getenv("GODADDY_ALLOW_DNS_WRITE", "0") == "1"


def dns_plan(domain: str) -> dict[str, object]:
    """Data only: the records that point the domain at the Saarthi server."""
    ip = (os.getenv("SAARTHI_SERVER_IP") or "").strip()
    if not ip:
        return {"domain": domain, "records": [], "note": "SAARTHI_SERVER_IP is not configured, so no records can be planned."}
    records = [DnsRecord("A", "@", ip), DnsRecord("CNAME", "www", "@")]
    return {"domain": domain, "records": [r.__dict__ for r in records],
            "note": "Nothing is changed until you confirm the domain and apply these records."}


class GoDaddyProvider:
    def __init__(self) -> None:
        self.key = os.getenv("GODADDY_API_KEY", "")
        self.secret = os.getenv("GODADDY_API_SECRET", "")
        self.base = os.getenv("GODADDY_API_BASE", "https://api.godaddy.com").rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"sso-key {self.key}:{self.secret}", "Accept": "application/json"}

    def check(self, domain: str) -> DomainCheck:
        if not self.key or not self.secret:
            return DomainCheck(domain, "unknown", reason="GoDaddy credentials are not configured")
        try:
            r = httpx.request("GET", f"{self.base}/v1/domains/available", params={"domain": domain, "checkType": "FAST"},
                              headers=self._headers(), timeout=TIMEOUT)
        except httpx.HTTPError:
            return DomainCheck(domain, "unknown", reason="GoDaddy could not be reached")
        if r.status_code in (401, 403):
            return DomainCheck(domain, "unknown", reason="GoDaddy rejected the credentials")
        if r.status_code != 200:
            return DomainCheck(domain, "unknown", reason=f"GoDaddy returned status {r.status_code}")
        try:
            body = r.json()
            available = bool(body["available"])
        except (ValueError, KeyError, TypeError):
            return DomainCheck(domain, "unknown", reason="GoDaddy returned an unexpected response")
        micros = body.get("price")
        price = round(micros / 1_000_000, 2) if available and isinstance(micros, (int, float)) else None
        return DomainCheck(domain, "available" if available else "taken", price, body.get("currency") if price is not None else None)

    def apply_records(self, domain: str, records: list[DnsRecord]) -> None:
        if not self.key or not self.secret:
            raise DnsWriteError("GoDaddy credentials are not configured")
        for rec in records:  # replaces only the record set for that type and name
            try:
                r = httpx.request("PUT", f"{self.base}/v1/domains/{domain}/records/{rec.type}/{rec.name}",
                                  json=[{"data": rec.data, "ttl": rec.ttl}], headers=self._headers(), timeout=TIMEOUT)
            except httpx.HTTPError as exc:
                raise DnsWriteError("GoDaddy could not be reached") from exc
            if r.status_code not in (200, 204):
                raise DnsWriteError(f"GoDaddy rejected the {rec.type} record (status {r.status_code})")


def get_provider() -> DomainProvider:
    return GoDaddyProvider()
