"""Track semantic observation streams discovered across coordinator refreshes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import SemanticObservation

_FRESHNESS_ATTRIBUTE_MAP = {
    "_open_data_freshness_status": "freshness_status",
    "_open_data_observation_age_seconds": "observation_age_seconds",
    "_open_data_observation_stale_after_seconds": "observation_stale_after_seconds",
}


@dataclass(slots=True)
class ObservationStreamTracker:
    """Remember materialized streams and return only newly observed IDs.

    Streams are intentionally never removed from this tracker during a running
    config entry. A temporarily sparse provider response therefore cannot cause
    existing Home Assistant entities to be pruned or recreated.
    """

    known_stream_ids: set[str] = field(default_factory=set)

    @classmethod
    def from_initial(
        cls, observations: Mapping[str, SemanticObservation]
    ) -> ObservationStreamTracker:
        """Create a tracker seeded from the platform's initial snapshot."""
        return cls(set(observations))

    def newly_observed(
        self, observations: Mapping[str, SemanticObservation]
    ) -> tuple[str, ...]:
        """Return deterministic new stream IDs and mark them as known."""
        discovered = tuple(
            stream_id
            for stream_id in sorted(observations)
            if stream_id not in self.known_stream_ids
        )
        self.known_stream_ids.update(discovered)
        return discovered


def observation_metadata_attributes(
    observation: SemanticObservation,
) -> dict[str, Any]:
    """Expose source-provided semantic metadata without altering identity."""
    attributes: dict[str, Any] = {}
    if observation.unit is not None:
        attributes["source_unit"] = observation.unit
    if observation.dimensions:
        dimensions: dict[str, str] = {}
        for field, value in observation.dimensions:
            attribute = _FRESHNESS_ATTRIBUTE_MAP.get(field)
            if attribute is None:
                dimensions[field] = value
                continue
            if attribute == "freshness_status":
                attributes[attribute] = value
                attributes["observation_stale"] = value == "stale"
            else:
                try:
                    attributes[attribute] = float(value)
                except (TypeError, ValueError):
                    attributes[attribute] = value
        if dimensions:
            attributes["dimensions"] = dimensions
    return attributes
