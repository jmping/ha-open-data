"""Estimate conservative polling intervals from metadata hints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PollingPlan:
    interval_seconds: int
    confidence: int
    reasons: tuple[str, ...] = ()


def infer_polling_plan(*, declared_seconds: int | None = None, live: bool = False, temporal: bool = False) -> PollingPlan:
    """Return a bounded deterministic polling interval."""
    if declared_seconds is not None and declared_seconds > 0:
        interval = min(86400, max(30, declared_seconds))
        return PollingPlan(interval, 95, ("declared update interval",))
    if live:
        return PollingPlan(60, 70, ("live dataset",))
    if temporal:
        return PollingPlan(300, 60, ("temporal dataset",))
    return PollingPlan(3600, 50, ("static or unknown cadence",))
