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
    """Evaluate one observation independently of fresher sibling streams.

    A missing timestamp remains an explicit ``unknown`` result. It is not marked
    stale automatically because many useful static datasets do not publish an
    observation timestamp at all.
    """
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
    """Return only streams that are not demonstrably stale.

    A stream's own bounded history is the preferred cadence source; the dataset
    cadence is only a fallback. This prevents one dead metric from inheriting the
    apparent recency of active siblings. Untimed observations remain usable with
    an explicit unknown freshness state.

    Existing Home Assistant entities are not deleted when a stream later becomes
    stale: the sensor platform intentionally keeps previously discovered stream
    identities. The suppression primarily prevents stale streams from being
    materialized during initial setup and yields ``unknown`` while they are stale.
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
        if state.stale is True:
            continue
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
        result[stream_id] = replace(observation, dimensions=dimensions)
    return result
