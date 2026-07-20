"""Provider-neutral timestamp field detection."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_STRONG_NAMES = {
    "timestamp",
    "datetime",
    "date_time",
    "observed_at",
    "observation_time",
    "measured_at",
    "recorded_at",
    "updated_at",
}
_DATE_NAMES = {"date", "observation_date", "record_date"}
_TIME_NAMES = {"time", "observation_time", "record_time"}
_TEMPORAL_TYPES = {"date", "datetime", "timestamp", "timestamptz"}
_NEGATIVE_TOKENS = {"timezone", "time_zone", "utc_offset", "duration"}


@dataclass(frozen=True, slots=True)
class TimestampCandidate:
    """A ranked timestamp field candidate."""

    name: str
    score: int
    reasons: tuple[str, ...]


def rank_timestamp_fields(
    fields: Iterable[tuple[str, str | None, str | None]],
) -> tuple[TimestampCandidate, ...]:
    """Rank ``(name, label, data_type)`` field descriptors."""
    candidates = [
        candidate
        for name, label, data_type in fields
        if (candidate := score_timestamp_field(name, label, data_type)).score > 0
    ]
    return tuple(sorted(candidates, key=lambda item: (-item.score, item.name.casefold())))


def score_timestamp_field(
    name: str, label: str | None = None, data_type: str | None = None
) -> TimestampCandidate:
    """Score one field as a likely event or observation timestamp."""
    normalized_name = _normalize(name)
    normalized_label = _normalize(label or "")
    normalized_type = _normalize(data_type or "")
    combined = {normalized_name, normalized_label}
    score = 0
    reasons: list[str] = []

    if normalized_type in _TEMPORAL_TYPES:
        score += 50
        reasons.append("temporal type")
    if combined & _STRONG_NAMES:
        score += 45
        reasons.append("strong timestamp name")
    elif combined & _DATE_NAMES:
        score += 25
        reasons.append("date-like name")
    elif combined & _TIME_NAMES:
        score += 15
        reasons.append("time-like name")

    tokens = set(normalized_name.split("_")) | set(normalized_label.split("_"))
    if {"observed", "recorded", "measured", "updated"} & tokens:
        score += 15
        reasons.append("observation timing token")
    if _NEGATIVE_TOKENS & combined or "duration" in tokens:
        score -= 60
        reasons.append("non-event temporal field")

    return TimestampCandidate(name=name, score=max(score, 0), reasons=tuple(reasons))


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
