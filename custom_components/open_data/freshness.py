"""Per-stream freshness decisions for normalized observations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Mapping

from .models import SemanticObservation
from .refresh_policy import parse_timestamp, stale_lag_threshold

_FRESHNESS_DIMENSIONS = {
    "_open_data_freshness_status",
    "_open_data_observation_age_seconds",
    "_open_data_observation_stale_after_seconds",
}


@dataclass(frozen=True, slots=True)
class ObservationFreshness:
    """Freshness state for one stable location/metric stream."""

    observed_at: datetime | None
    checked_at: datetime
    age_seconds: float | None
    stale_after_seconds: float
    stale: bool | None

    @property
    def available(self) -> bool:
        """Return whether the value is known not to be stale."""
        return self.stale is not True

    @property
    def status(self) -> str:
        """Return a stable diagnostic status."""
        if self.stale is True:
            return "stale"
        if self.stale is False:
            return "current"
        return "unknown"


def _latest_observed_at(observation: SemanticObservation | None) -> datetime | None:
    """Return the newest valid timestamp carried by one observation."""
    if observation is None:
        return None
    timestamps = [parse_timestamp(observation.timestamp)]
    timestamps.extend(parse_timestamp(point.timestamp) for point in observation.history)
    valid = [timestamp for timestamp in timestamps if timestamp is not None]
    return max(valid, default=None)


def _stream_frequency_seconds(observation: SemanticObservation) -> float | None:
    """Estimate one stream's own recent cadence from bounded history."""
    timestamps = sorted(
        {
            parsed
            for point in observation.history
            if (parsed := parse_timestamp(point.timestamp)) is not None
        }
    )
    gaps = [
        (right - left).total_seconds()
        for left, right in zip(timestamps, timestamps[1:])
        if right > left
    ]
    if not gaps:
        return None
    return float(median(gaps[-30:]))


def observation_freshness(
    observation: SemanticObservation | None,
    frequency_seconds: float | None,
    *,
    checked_at: object = None,
) -> ObservationFreshness:
    """Evaluate one observation independently of fresher sibling streams."""
    checked = parse_timestamp(checked_at) or datetime.now(timezone.utc)
    observed = _latest_observed_at(observation)
    frequency = (
        None
        if frequency_seconds is None
        else timedelta(seconds=max(0.0, frequency_seconds))
    )
    threshold = stale_lag_threshold(frequency)
    if observed is None:
        return ObservationFreshness(
            observed_at=None,
            checked_at=checked,
            age_seconds=None,
            stale_after_seconds=threshold.total_seconds(),
            stale=None,
        )
    age = max(0.0, (checked - observed).total_seconds())
    return ObservationFreshness(
        observed_at=observed,
        checked_at=checked,
        age_seconds=age,
        stale_after_seconds=threshold.total_seconds(),
        stale=age >= threshold.total_seconds(),
    )


def freshness_attributes(state: ObservationFreshness) -> dict[str, object]:
    """Return Home Assistant-safe diagnostic attributes."""
    attributes: dict[str, object] = {
        "freshness_status": state.status,
        "observation_stale_after_seconds": round(state.stale_after_seconds, 1),
    }
    if state.observed_at is not None:
        attributes["observed_at"] = state.observed_at.isoformat()
    if state.age_seconds is not None:
        attributes["observation_age_seconds"] = round(state.age_seconds, 1)
    if state.stale is not None:
        attributes["observation_stale"] = state.stale
    return attributes


def apply_observation_freshness(
    observations: Mapping[str, SemanticObservation],
    frequency_seconds: float | None,
    *,
    checked_at: object = None,
) -> dict[str, SemanticObservation]:
    """Mask demonstrably stale values while retaining their history and identity.

    A stream's own bounded history is the preferred cadence source; dataset cadence
    is only a fallback. This lets configuration exclude stale measures by default
    while still allowing an explicit opt-in for historical use. An opted-in stale
    stream remains present, imports its history, and reports an unavailable current
    state instead of presenting an old observation as current.
    """
    result: dict[str, SemanticObservation] = {}
    for stream_id, observation in observations.items():
        stream_frequency = _stream_frequency_seconds(observation)
        effective_frequency = (
            stream_frequency if stream_frequency is not None else frequency_seconds
        )
        state = observation_freshness(
            observation, effective_frequency, checked_at=checked_at
        )
        dimensions = tuple(
            item for item in observation.dimensions if item[0] not in _FRESHNESS_DIMENSIONS
        )
        dimensions += (
            ("_open_data_freshness_status", state.status),
            (
                "_open_data_observation_stale_after_seconds",
                str(round(state.stale_after_seconds, 1)),
            ),
        )
        if state.age_seconds is not None:
            dimensions += (
                (
                    "_open_data_observation_age_seconds",
                    str(round(state.age_seconds, 1)),
                ),
            )
        result[stream_id] = replace(
            observation,
            value=None if state.stale is True else observation.value,
            dimensions=dimensions,
        )
    return result
