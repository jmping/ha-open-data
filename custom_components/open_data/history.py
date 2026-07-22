"""Bounded observation history and source-freshness helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .models import ObservationPoint, OpenDataDataset, SemanticObservation
from .refresh_policy import infer_frequency, parse_timestamp, stale_lag_threshold


def dataset_source_updated_at(dataset: OpenDataDataset) -> str | None:
    """Return the newest known portal/file modification timestamp."""
    raw = dataset.raw
    selected = raw.get("_selected_resource")
    candidates: list[object] = []
    for mapping in (raw, selected if isinstance(selected, dict) else {}):
        for key in (
            "last_modified",
            "metadata_modified",
            "updated_at",
            "modified",
            "rowsUpdatedAt",
        ):
            if mapping.get(key) not in (None, ""):
                candidates.append(mapping[key])
    parsed = [value for value in (parse_timestamp(item) for item in candidates) if value]
    return max(parsed).isoformat() if parsed else None


def snapshot_freshness(
    dataset: OpenDataDataset,
    observations: Mapping[str, SemanticObservation],
) -> tuple[str | None, str | None, float | None]:
    """Summarize newest observation, source modification, and typical cadence."""
    timestamps = [
        point.timestamp
        for observation in observations.values()
        for point in observation.history
    ]
    parsed = [value for value in (parse_timestamp(item) for item in timestamps) if value]
    newest = max(parsed).isoformat() if parsed else None
    frequency = infer_frequency(timestamps)
    return (
        newest,
        dataset_source_updated_at(dataset),
        frequency.total_seconds() if frequency is not None else None,
    )


def is_stale(
    latest_observation_at: object,
    frequency_seconds: float | None,
    *,
    now: datetime | None = None,
) -> bool | None:
    """Report staleness using the same five-wave/30-minute source policy."""
    latest = parse_timestamp(latest_observation_at)
    if latest is None:
        return None
    current = now or datetime.now(timezone.utc)
    frequency = (
        None
        if frequency_seconds is None
        else timedelta(seconds=frequency_seconds)
    )
    return current - latest >= stale_lag_threshold(frequency)


def interval_statistics(
    points: Iterable[ObservationPoint], *, minutes: int
) -> list[dict[str, Any]]:
    """Aggregate numeric source points into aligned HA statistics buckets."""
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for point in points:
        timestamp = parse_timestamp(point.timestamp)
        if timestamp is None:
            continue
        start = timestamp.replace(
            minute=(timestamp.minute // minutes) * minutes,
            second=0,
            microsecond=0,
        )
        buckets[start].append(float(point.value))
    return [
        {
            "start": start,
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }
        for start, values in sorted(buckets.items())
    ]


def hourly_statistics(points: Iterable[ObservationPoint]) -> list[dict[str, Any]]:
    """Aggregate bounded numeric source points into hourly long-term means."""
    return interval_statistics(points, minutes=60)
