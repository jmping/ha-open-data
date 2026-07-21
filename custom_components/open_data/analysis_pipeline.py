"""Two-pass dataset analysis using structural and historical samples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .analyzer import DatasetStructure, analyze_dataset
from .models import OpenDataDataset
from .observation_model import ObservationModel, analyze_observations
from .providers.base import OpenDataProvider


@dataclass(frozen=True, slots=True)
class DatasetAnalysis:
    """Combined structural and observation interpretation of a dataset."""

    structure: DatasetStructure
    observations: ObservationModel
    rows: tuple[dict[str, Any], ...]
    initial_row_count: int
    historical_row_count: int


async def async_analyze_dataset(
    provider: OpenDataProvider,
    dataset: OpenDataDataset,
    *,
    initial_limit: int = 50,
    entity_limit: int = 20,
    observations_per_entity: int = 25,
) -> DatasetAnalysis:
    """Analyze a dataset in two passes.

    The first bounded sample identifies candidate entity and timestamp fields. The
    second sample asks the provider to distribute historical observations across
    those candidates, then reruns both structural and observation-shape analysis.
    """
    initial_rows = await provider.async_sample_rows(
        dataset.dataset_id,
        dataset.resource_id,
        limit=initial_limit,
    )
    initial_structure = analyze_dataset(dataset, initial_rows)

    historical_rows = await provider.async_sample_observations(
        dataset.dataset_id,
        dataset.resource_id,
        entity_field=initial_structure.identity_field,
        timestamp_field=initial_structure.timestamp_field,
        entity_limit=entity_limit,
        observations_per_entity=observations_per_entity,
    )
    rows = historical_rows or initial_rows

    return DatasetAnalysis(
        structure=analyze_dataset(dataset, rows),
        observations=analyze_observations(dataset, rows),
        rows=tuple(rows),
        initial_row_count=len(initial_rows),
        historical_row_count=len(historical_rows),
    )
