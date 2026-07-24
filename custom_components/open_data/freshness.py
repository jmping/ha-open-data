"""Per-stream freshness decisions for normalized observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import SemanticObservation
from .refresh_policy import parse_timestamp, stale_lag_threshold


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
        """Return whether the value is safe to present as current."""
        return self.stale is False


def observation_freshness(
    observation: SemanticObservation | None,
    frequency_seconds: float | None,
    *,
    checked_at: object = None,
) -> ObservationFreshness:
    """Evaluate one observation independently of fresher sibling streams.

    Missing or unparseable timestamps are deliberately not considered current.
    The threshold follows the integration-wide policy of five missed update waves,
    with the existing thirty-minute minimum when cadence is unknown or very fast.
    """
    checked = parse_timestamp(checked_at) or datetime.now(timezone.utc)
    observed = parse_timestamp(observation.timestamp) if observation else None
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
        "observation_stale_after_seconds": round(state.stale_after_seconds, 1),
    }
    if state.observed_at is not None:
        attributes["observed_at"] = state.observed_at.isoformat()
    if state.age_seconds is not None:
        attributes["observation_age_seconds"] = round(state.age_seconds, 1)
    if state.stale is not None:
        attributes["observation_stale"] = state.stale
    return attributes
