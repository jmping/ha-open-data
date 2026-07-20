"""High-level dataset intelligence inference."""

from __future__ import annotations

from dataclasses import dataclass

from .dataset_profile import DatasetProfile


@dataclass(frozen=True, slots=True)
class DatasetIntelligence:
    """Provider-neutral dataset characteristics."""

    temporal: bool
    spatial: bool
    tabular: bool
    observations: bool
    station_metadata: bool
    score: int
    reasons: tuple[str, ...]


def infer_dataset_intelligence(profile: DatasetProfile) -> DatasetIntelligence:
    """Infer broad dataset characteristics from a structural profile."""
    temporal = profile.timestamp is not None
    spatial = profile.geometry is not None or (
        profile.latitude is not None and profile.longitude is not None
    )
    observations = temporal and bool(profile.measures)
    station_metadata = profile.identifier is not None and spatial and not temporal
    reasons = tuple(
        reason
        for condition, reason in (
            (temporal, "timestamp field"),
            (spatial, "spatial fields"),
            (bool(profile.measures), "measurement fields"),
            (profile.identifier is not None, "identifier field"),
        )
        if condition
    )
    score = min(100, sum((25 if temporal else 0, 25 if spatial else 0, 30 if observations else 0, 20 if profile.identifier else 0)))
    return DatasetIntelligence(temporal, spatial, True, observations, station_metadata, score, reasons)
