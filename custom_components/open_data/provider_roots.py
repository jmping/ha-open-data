"""Bounded alternate API roots for known provider deployment layouts."""

from __future__ import annotations


PROVIDER_CKAN = "ckan"


def provider_roots(provider_name: str, portal_url: str) -> tuple[str, ...]:
    """Return tightly bounded alternate API roots for known deployment layouts.

    Some CKAN installations serve their public site at the host root while the
    CKAN application itself is mounted at ``/data``. Trying exactly that
    conventional subpath after the supplied root is safe and deterministic; other
    provider families receive no speculative path expansion.
    """
    normalized = portal_url.rstrip("/")
    roots = [normalized]
    if provider_name == PROVIDER_CKAN and not normalized.casefold().endswith("/data"):
        roots.append(f"{normalized}/data")
    return tuple(roots)
