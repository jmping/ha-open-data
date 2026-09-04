"""Per-measure update-history profiling for import and presentation decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .refresh_policy import stale_lag_threshold
from .temporal import normalize_row_timestamps, parse_flexible_timestamp, TemporalContext


@dataclass(frozen=True, slots=True)
class MeasureFreshnessProfile:
    """Bounded recency and cadence evidence for one metric field."""

    field: str
    observation_count: int
    latest_observation_at: str | None
    oldest_observation_at: str | None
    cadence_seconds: float | None
    age_seconds: float | None
    peer_lag_seconds: float | None
    stale_after_seconds: float | None
    status: str
    presentation: str
    auto_import: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def chooser_suffix(self) -> str:
        """Return compact human-readable recency evidence for selectors."""
        if self.latest_observation_at is None:
            return "recency unknown"
        latest = datetime.fromisoformat(self.latest_observation_at)
        age = self.age_seconds or 0.0
        if age < 3600:
            age_label = f"{max(1, round(age / 60))}m ago"
        elif age < 172800:
            age_label = f"{max(1, round(age / 3600))}h ago"
        else:
            age_label = f"{max(1, round(age / 86400))}d ago"
        cadence = ""
        if self.cadence_seconds is not None:
            seconds = self.cadence_seconds
            if seconds < 3600:
                cadence = f", ~{max(1, round(seconds / 60))}m cadence"
            elif seconds < 172800:
                cadence = f", ~{max(1, round(seconds / 3600))}h cadence"
            else:
                cadence = f", ~{max(1, round(seconds / 86400))}d cadence"
        return f"{self.status}, {age_label}{cadence}"


def _median_cadence(values: Sequence[datetime]) -> float | None:
    unique = sorted(set(values))
    gaps = [
        (right - left).total_seconds()
        for left, right in zip(unique, unique[1:])
        if right > left
    ]
    if not gaps:
        return None
    return float(median(gaps[-30:]))


def _presentation(cadence: float | None, observation_count: int, status: str) -> str:
    if status == "stale":
        return "historical"
    if observation_count < 2:
        return "latest_value"
    if cadence is None:
        return "history"
    if cadence <= 6 * 3600:
        return "recent_history"
    if cadence <= 7 * 86400:
        return "trend"
    return "historical_trend"


def build_measure_freshness_profiles(
    rows: Sequence[Mapping[str, Any]],
    *,
    metric_fields: Sequence[str],
    timestamp_fields: Sequence[str],
    timezone_name: str,
    now: datetime | None = None,
) -> dict[str, MeasureFreshnessProfile]:
    """Profile each metric independently and identify lagging/dead streams.

    The newest sibling stream is used as a relative reference so one measure that
    stopped updating is suppressed even when the dataset itself is still active.
    Absolute age is evaluated against the stream's own cadence when enough history
    exists. Untimed fields remain available because static datasets may be useful.
    """
    zone = ZoneInfo(timezone_name)
    checked = now.astimezone(zone) if now is not None else datetime.now(zone)
    normalized, _plan, canonical = normalize_row_timestamps(
        rows,
        timezone_name=timezone_name,
        now=checked,
    )
    context = TemporalContext(checked, timezone_name)

    timestamps_by_field: dict[str, list[datetime]] = {field: [] for field in metric_fields}
    for row in normalized:
        timestamp: datetime | None = None
        if canonical and row.get(canonical) not in (None, ""):
            timestamp = parse_flexible_timestamp(row.get(canonical), context)
        if timestamp is None:
            for timestamp_field in timestamp_fields:
                timestamp = parse_flexible_timestamp(row.get(timestamp_field), context)
                if timestamp is not None:
                    break
        if timestamp is None:
            continue
        for field in metric_fields:
            if row.get(field) not in (None, ""):
                timestamps_by_field[field].append(timestamp)

    latest_by_field = {
        field: max(values)
        for field, values in timestamps_by_field.items()
        if values
    }
    peer_latest = max(latest_by_field.values(), default=None)
    cadences = {
        field: _median_cadence(values)
        for field, values in timestamps_by_field.items()
    }
    known_cadences = [value for value in cadences.values() if value is not None]
    peer_cadence = float(median(known_cadences)) if known_cadences else None

    result: dict[str, MeasureFreshnessProfile] = {}
    for field in metric_fields:
        values = timestamps_by_field[field]
        latest = max(values, default=None)
        oldest = min(values, default=None)
        cadence = cadences[field]
        reference_cadence = cadence if cadence is not None else peer_cadence
        threshold = stale_lag_threshold(
            timedelta(seconds=reference_cadence) if reference_cadence is not None else None
        ).total_seconds()
        age = max(0.0, (checked - latest).total_seconds()) if latest else None
        peer_lag = (
            max(0.0, (peer_latest - latest).total_seconds())
            if latest is not None and peer_latest is not None
            else None
        )

        # Relative lag is the strongest signal for partially abandoned datasets:
        # if sibling measures continue to update but this one has missed at least
        # five expected waves, do not auto-import it. Absolute lag adds protection
        # for an otherwise-live feed where every recent sample for one measure is old.
        stale_relative = peer_lag is not None and peer_lag >= threshold
        stale_absolute = (
            age is not None
            and reference_cadence is not None
            and age >= threshold
        )
        stale = stale_relative or stale_absolute
        if latest is None:
            status = "unknown"
        elif stale:
            status = "stale"
        elif peer_lag and peer_lag > 0:
            status = "lagging"
        else:
            status = "current"

        result[field] = MeasureFreshnessProfile(
            field=field,
            observation_count=len(values),
            latest_observation_at=latest.isoformat() if latest else None,
            oldest_observation_at=oldest.isoformat() if oldest else None,
            cadence_seconds=cadence,
            age_seconds=age,
            peer_lag_seconds=peer_lag,
            stale_after_seconds=threshold if latest else None,
            status=status,
            presentation=_presentation(cadence, len(values), status),
            auto_import=not stale,
        )
    return result


def serializable_profiles(
    profiles: Mapping[str, MeasureFreshnessProfile],
) -> dict[str, dict[str, Any]]:
    """Return Home Assistant config-entry-safe freshness data."""
    return {field: profile.as_dict() for field, profile in profiles.items()}
