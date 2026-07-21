"""Adaptive dataset analysis using structural and historical samples."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Iterable

from .analyzer import DatasetStructure, analyze_dataset
from .models import OpenDataDataset
from .observation_model import ObservationModel, ObservationShape, analyze_observations
from .providers.base import OpenDataProvider

_DEFAULT_SAMPLE_STAGES = (200, 1000, 20000)
_MINIMUM_STAGES = 2
_GROWTH_THRESHOLD = 0.08


@dataclass(frozen=True, slots=True)
class SamplingStageReport:
    """Evidence and convergence data for one adaptive sampling stage."""

    requested_rows: int
    retrieved_rows: int
    entity_count: int
    metric_value_count: int
    observation_dimension_value_count: int
    shape: str
    confidence: float
    structural_growth: float


@dataclass(frozen=True, slots=True)
class SamplingReport:
    """Explain why adaptive sampling stopped and how much evidence was used."""

    stages: tuple[SamplingStageReport, ...]
    converged: bool
    stopped_reason: str
    requested_row_cap: int
    retrieved_row_count: int


@dataclass(frozen=True, slots=True)
class DatasetAnalysis:
    """Combined structural and observation interpretation of a dataset."""

    structure: DatasetStructure
    observations: ObservationModel
    rows: tuple[dict[str, Any], ...]
    initial_row_count: int
    historical_row_count: int
    sampling: SamplingReport


def _row_key(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Create a stable key suitable for merging overlapping provider samples."""
    return tuple(sorted((str(key), repr(value)) for key, value in row.items()))


def _merge_rows(
    existing: Iterable[dict[str, Any]], incoming: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    found = {_row_key(row): row for row in existing}
    for row in incoming:
        found.setdefault(_row_key(row), row)
    return list(found.values())


def _distinct_values(rows: list[dict[str, Any]], fields: Iterable[str]) -> int:
    return sum(
        len(
            {
                str(row[field])
                for row in rows
                if row.get(field) not in (None, "")
            }
        )
        for field in fields
    )


def _coverage_signature(
    model: ObservationModel, rows: list[dict[str, Any]]
) -> tuple[int, int, int]:
    entity_count = _distinct_values(rows, model.entity_fields[:1])
    metric_value_count = _distinct_values(rows, model.metric_dimension_fields)
    dimension_value_count = _distinct_values(rows, model.observation_dimension_fields)
    return entity_count, metric_value_count, dimension_value_count


def _growth(previous: tuple[int, int, int], current: tuple[int, int, int]) -> float:
    """Return the largest relative increase among lower-level semantic dimensions."""
    increases = []
    for before, after in zip(previous, current, strict=True):
        if before == 0:
            increases.append(1.0 if after > 0 else 0.0)
        else:
            increases.append(max(0.0, (after - before) / before))
    return max(increases, default=0.0)


def _needs_deep_sample(
    model: ObservationModel,
    growth: float,
    retrieved_rows: int,
    requested_rows: int,
) -> bool:
    """Escalate only when more rows are likely to reveal meaningful granularity."""
    if retrieved_rows < requested_rows:
        return False
    if model.shape == ObservationShape.UNKNOWN or model.confidence < 0.75:
        return True
    if growth >= _GROWTH_THRESHOLD:
        return True
    return False


async def async_analyze_dataset(
    provider: OpenDataProvider,
    dataset: OpenDataDataset,
    *,
    initial_limit: int = 200,
    entity_limit: int = 20,
    sample_stages: tuple[int, ...] = _DEFAULT_SAMPLE_STAGES,
) -> DatasetAnalysis:
    """Analyze a dataset with adaptive, convergence-aware historical sampling.

    A 200-row structural sample identifies candidate entity and timestamp fields.
    Historical sampling then grows to 1,000 rows. It escalates to the 20,000-row
    deep stage only when lower-level metric or observation dimensions are still
    expanding, or when the inferred observation model remains uncertain.
    """
    stages = tuple(sorted({max(1, int(value)) for value in sample_stages}))
    if not stages:
        raise ValueError("At least one adaptive sampling stage is required")

    first_limit = max(initial_limit, stages[0])
    initial_rows = await provider.async_sample_rows(
        dataset.dataset_id,
        dataset.resource_id,
        limit=first_limit,
    )
    initial_structure = analyze_dataset(dataset, initial_rows)

    rows = list(initial_rows)
    reports: list[SamplingStageReport] = []
    previous_signature: tuple[int, int, int] | None = None
    converged = False
    stopped_reason = "sample_cap_reached"

    for index, requested_rows in enumerate(stages):
        observations_per_entity = max(1, ceil(requested_rows / max(entity_limit, 1)))
        sampled = await provider.async_sample_observations(
            dataset.dataset_id,
            dataset.resource_id,
            entity_field=initial_structure.identity_field,
            timestamp_field=initial_structure.timestamp_field,
            entity_limit=entity_limit,
            observations_per_entity=observations_per_entity,
        )
        rows = _merge_rows(rows, sampled)
        model = analyze_observations(dataset, rows)
        signature = _coverage_signature(model, rows)
        growth = (
            _growth(previous_signature, signature)
            if previous_signature is not None
            else 1.0
        )
        reports.append(
            SamplingStageReport(
                requested_rows=requested_rows,
                retrieved_rows=len(rows),
                entity_count=signature[0],
                metric_value_count=signature[1],
                observation_dimension_value_count=signature[2],
                shape=model.shape.value,
                confidence=model.confidence,
                structural_growth=round(growth, 3),
            )
        )

        provider_exhausted = len(sampled) < requested_rows
        if provider_exhausted:
            converged = True
            stopped_reason = "provider_exhausted"
            break

        minimum_complete = index + 1 >= min(_MINIMUM_STAGES, len(stages))
        if minimum_complete and not _needs_deep_sample(
            model, growth, len(sampled), requested_rows
        ):
            converged = True
            stopped_reason = "structural_convergence"
            break

        previous_signature = signature

    final_structure = analyze_dataset(dataset, rows)
    final_observations = analyze_observations(dataset, rows)
    return DatasetAnalysis(
        structure=final_structure,
        observations=final_observations,
        rows=tuple(rows),
        initial_row_count=len(initial_rows),
        historical_row_count=max(0, len(rows) - len(initial_rows)),
        sampling=SamplingReport(
            stages=tuple(reports),
            converged=converged,
            stopped_reason=stopped_reason,
            requested_row_cap=stages[-1],
            retrieved_row_count=len(rows),
        ),
    )
