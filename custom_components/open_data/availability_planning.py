"""Plan entity availability from observation freshness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class AvailabilityState(StrEnum):
    AVAILABLE = "available"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AvailabilityPlan:
    state: AvailabilityState
    stale_after_seconds: int
    reasons: tuple[str, ...] = ()


def plan_availability(
    *,
    observed_at: datetime | None,
    poll_interval_seconds: int,
    now: datetime | None = None,
    multiplier: int = 3,
) -> AvailabilityPlan:
    """Classify freshness using a poll-derived staleness window."""
    stale_after = max(60, poll_interval_seconds * max(1, multiplier))
    if observed_at is None:
        return AvailabilityPlan(AvailabilityState.UNKNOWN, stale_after, ("missing observation timestamp",))
    reference = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    age = reference.astimezone(UTC) - observed_at.astimezone(UTC)
    if age > timedelta(seconds=stale_after):
        return AvailabilityPlan(AvailabilityState.STALE, stale_after, ("observation older than staleness window",))
    return AvailabilityPlan(AvailabilityState.AVAILABLE, stale_after, ("observation within staleness window",))
