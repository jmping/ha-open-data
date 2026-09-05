"""Failure classification and circuit-breaker state for public-data refreshes."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

import aiohttp

from .providers.base import OpenDataConnectionError, OpenDataError


@dataclass(slots=True, frozen=True)
class RuntimeFailure:
    """One normalized refresh failure suitable for diagnostics and UI state."""

    stage: str
    error_type: str
    message: str
    fingerprint: str
    transient: bool
    occurrences: int
    suspended: bool
    first_seen_at: str
    last_seen_at: str


def is_transient_failure(err: BaseException) -> bool:
    """Return whether retrying later is likely to succeed without reconfiguration."""
    return isinstance(
        err,
        (
            asyncio.TimeoutError,
            TimeoutError,
            aiohttp.ClientError,
            OpenDataConnectionError,
        ),
    ) or (isinstance(err, OpenDataError) and "timeout" in str(err).casefold())


def failure_fingerprint(stage: str, err: BaseException) -> str:
    """Return a stable, non-sensitive identity for repeated equivalent failures."""
    payload = f"{stage}|{type(err).__name__}|{str(err)[:240]}"
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]


def next_failure(
    *,
    stage: str,
    err: BaseException,
    previous: RuntimeFailure | None,
    transient_retry_limit: int = 3,
) -> RuntimeFailure:
    """Build the next circuit-breaker state for one failed refresh."""
    now = datetime.now(timezone.utc).isoformat()
    fingerprint = failure_fingerprint(stage, err)
    transient = is_transient_failure(err)
    same = previous is not None and previous.fingerprint == fingerprint
    occurrences = previous.occurrences + 1 if same else 1
    first_seen = previous.first_seen_at if same else now
    suspended = (not transient) or occurrences >= transient_retry_limit
    return RuntimeFailure(
        stage=stage,
        error_type=type(err).__name__,
        message=str(err)[:500],
        fingerprint=fingerprint,
        transient=transient,
        occurrences=occurrences,
        suspended=suspended,
        first_seen_at=first_seen,
        last_seen_at=now,
    )
