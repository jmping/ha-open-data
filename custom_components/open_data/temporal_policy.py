"""Timestamp uncertainty and timezone-resolution policy for open-data analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .temporal import TemporalContext, TemporalPlan, infer_temporal_plan


@dataclass(frozen=True, slots=True)
class TimezoneResolution:
    """One validated IANA timezone and the evidence that selected it."""

    timezone_name: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TemporalResolution:
    """Explain whether observation time could be resolved safely."""

    status: str
    timezone: TimezoneResolution
    plan: TemporalPlan | None
    warning: str | None = None

    @property
    def recency_available(self) -> bool:
        return self.plan is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "timezone": self.timezone.as_dict(),
            "plan": self.plan.as_dict() if self.plan is not None else None,
            "warning": self.warning,
        }


def _valid_timezone(value: str | None) -> str | None:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    try:
        ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return candidate


def resolve_timezone(
    *,
    source_timezone: str | None = None,
    user_timezone: str | None = None,
    home_assistant_timezone: str | None = None,
) -> TimezoneResolution:
    """Resolve naive civil timestamps without silently assuming UTC.

    Source metadata is authoritative when it supplies an IANA timezone. A user
    override is next because some public feeds document local civil time outside
    machine-readable metadata. Home Assistant's configured timezone is the safe
    local fallback. UTC is used only when no local context exists at all.
    """
    for value, source in (
        (source_timezone, "source"),
        (user_timezone, "user"),
        (home_assistant_timezone, "home_assistant"),
    ):
        resolved = _valid_timezone(value)
        if resolved is not None:
            return TimezoneResolution(resolved, source)
    return TimezoneResolution("UTC", "fallback_utc")


def resolve_temporal_plan(
    fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    *,
    source_timezone: str | None = None,
    user_timezone: str | None = None,
    home_assistant_timezone: str | None = None,
    now: datetime | None = None,
) -> TemporalResolution:
    """Infer one plan while preserving an explicit unknown-time outcome."""
    timezone = resolve_timezone(
        source_timezone=source_timezone,
        user_timezone=user_timezone,
        home_assistant_timezone=home_assistant_timezone,
    )
    zone = ZoneInfo(timezone.timezone_name)
    context = TemporalContext(
        now.astimezone(zone) if now is not None else datetime.now(zone),
        timezone.timezone_name,
    )
    plan = infer_temporal_plan(fields, rows, context)
    if plan is None:
        return TemporalResolution(
            status="unknown",
            timezone=timezone,
            plan=None,
            warning=(
                "No trustworthy observation timestamp could be inferred; "
                "freshness-based exclusion is disabled until time is configured."
            ),
        )
    return TemporalResolution("resolved", timezone, plan)
