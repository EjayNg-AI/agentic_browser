from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse


@dataclass
class DomainPolicy:
    mode: str
    domains: list[str]

    @classmethod
    def from_config(cls, mode: str, domains: Iterable[str]) -> "DomainPolicy":
        normalized = [normalize_domain(d) for d in domains if d]
        return cls(mode=mode, domains=normalized)

    def is_allowed(self, url: str) -> bool:
        host = extract_host(url)
        if not host:
            return True
        matched = any(matches_domain(host, domain) for domain in self.domains)
        if self.mode == "allowlist":
            return matched
        if self.mode == "denylist":
            return not matched
        return True


def normalize_domain(value: str) -> str:
    return value.strip().lower().lstrip(".")


def extract_host(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    if parsed.hostname:
        return parsed.hostname.lower()
    return None


def matches_domain(host: str, domain: str) -> bool:
    if host == domain:
        return True
    return host.endswith("." + domain)
