"""Source cadence and authoritative-file fallback policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Iterable

MINIMUM_STALE_LAG = timedelta(minutes=30)
STALE_FREQUENCY_WAVES = 5


def parse_timestamp(value: object) -> datetime | None:
    """Parse common ISO timestamps without imposing a provider dependency."""
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def infer_frequency(values: Iterable[object]) -> timedelta | None:
    """Infer the typical positive update interval from recent observations."""
    timestamps = sorted({item for value in values if (item := parse_timestamp(value))})
    gaps = [right - left for left, right in zip(timestamps, timestamps[1:]) if right > left]
    if not gaps:
        return None
    recent = gaps[-50:]
    return timedelta(seconds=median(gap.total_seconds() for gap in recent))


def stale_lag_threshold(frequency: timedelta | None) -> timedelta:
    """Require five missed waves, but never less than thirty minutes."""
    if frequency is None:
        return MINIMUM_STALE_LAG
    return max(MINIMUM_STALE_LAG, frequency * STALE_FREQUENCY_WAVES)


@dataclass(frozen=True, slots=True)
class SourceFreshness:
    """Decision inputs and result for an API-versus-file source."""

    frequency: timedelta | None
    api_latest: datetime | None
    authoritative_latest: datetime | None

    @property
    def fallback_required(self) -> bool:
        if self.api_latest is None or self.authoritative_latest is None:
            return True
        return self.authoritative_latest - self.api_latest >= stale_lag_threshold(
            self.frequency
        )

