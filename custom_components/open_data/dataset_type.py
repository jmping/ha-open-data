"""Infer broad dataset roles from provider-neutral metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .dataset_intelligence import DatasetIntelligence


class DatasetType(StrEnum):
    OBSERVATIONS = "observations"
    FORECAST = "forecast"
    STATION_METADATA = "station_metadata"
    EVENTS = "events"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True, slots=True)
class DatasetTypeInference:
    kind: DatasetType
    confidence: int
    reasons: tuple[str, ...]


def infer_dataset_type(
    intelligence: DatasetIntelligence,
    *,
    title: str = "",
    description: str = "",
) -> DatasetTypeInference:
    """Infer a dataset role using structure plus lightweight textual hints."""
    text = f"{title} {description}".casefold()
    if "forecast" in text or "prediction" in text:
        return DatasetTypeInference(DatasetType.FORECAST, 90, ("forecast metadata",))
    if intelligence.station_metadata:
        return DatasetTypeInference(
            DatasetType.STATION_METADATA, 85, ("identifier and location without timestamp",)
        )
    if intelligence.observations:
        return DatasetTypeInference(
            DatasetType.OBSERVATIONS, 85, ("timestamp and measurement fields",)
        )
    if "event" in text or "incident" in text:
        return DatasetTypeInference(DatasetType.EVENTS, 70, ("event metadata",))
    return DatasetTypeInference(DatasetType.SNAPSHOT, 40, ("no stronger dataset role",))
