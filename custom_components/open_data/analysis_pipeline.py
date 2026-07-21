"""Adaptive dataset analysis, population estimation, and retrieval planning."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import ceil
from typing import Any, Iterable

from .analyzer import DatasetStructure, analyze_dataset
from .models import OpenDataDataset
from .observation_model import ObservationModel, ObservationShape, analyze_observations
from .providers.base import OpenDataProvider

_DEFAULT_SAMPLE_STAGES = (200, 1000, 20000)
_MINIMUM_STAGES = 2
_GROWTH_THRESHOLD = 0.08


class DatasetOrdering(StrEnum):
    """Observed physical ordering of sampled rows."""

    TIME_ASCENDING = "time_ascending"
    TIME_DESCENDING = "time_descending"
    ENTITY_GROUPED = "entity_grouped"
    EFFECTIVELY_RANDOM = "effectively_random"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EntityPopulationEstimate:
    """Estimated entity population from sample frequency-of-frequencies."""

    observed_entities: int
    estimated_entities: int
    singletons: int
    doubletons: int
    sample_rows: int
    unseen_estimate: float
    confidence: float


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    """Plan for collecting representative history after semantic analysis."""

    ordering: DatasetOrdering
    estimated_entities: int
    target_observations_per_entity: int
    dimension_multiplier: int
    target_rows: int
    entity_limit: int
    observations_per_entity: int


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
    entity_population: EntityPopulationEstimate
    retrieval_plan: RetrievalPlan
    imported_row_count: int


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
        len({str(row[field]) for row in rows if row.get(field) not in (None, "")})
        for field in fields
    )


def _coverage_signature(
    model: ObservationModel, rows: list[dict[str, Any]]
) -> tuple[int, int, int]:
    return (
        _distinct_values(rows, model.entity_fields[:1]),
        _distinct_values(rows, model.metric_dimension_fields),
        _distinct_values(rows, model.observation_dimension_fields),
    )


def _growth(previous: tuple[int, int, int], current: tuple[int, int, int]) -> float:
    increases = []
    for before, after in zip(previous, current, strict=True):
        increases.append(1.0 if before == 0 and after > 0 else 0.0 if before == 0 else max(0.0, (after - before) / before))
    return max(increases, default=0.0)


def _needs_deep_sample(
    model: ObservationModel, growth: float, retrieved_rows: int, requested_rows: int
) -> bool:
    if retrieved_rows < requested_rows:
        return False
    return (
        model.shape == ObservationShape.UNKNOWN
        or model.confidence < 0.75
        or growth >= _GROWTH_THRESHOLD
    )


def estimate_entity_population(
    rows: list[dict[str, Any]], entity_field: str | None
) -> EntityPopulationEstimate:
    """Estimate total entities using the bias-corrected Chao1 lower bound.

    With a random or representative row sample, repeated sightings rapidly constrain
    the unseen population. A sample with 73 observed entities and few singletons
    therefore estimates approximately 73 entities, not hundreds.
    """
    if not entity_field:
        return EntityPopulationEstimate(0, 0, 0, 0, len(rows), 0.0, 0.0)
    frequencies = Counter(
        str(row[entity_field])
        for row in rows
        if row.get(entity_field) not in (None, "")
    )
    observed = len(frequencies)
    f1 = sum(count == 1 for count in frequencies.values())
    f2 = sum(count == 2 for count in frequencies.values())
    if observed == 0:
        unseen = 0.0
    elif f2 > 0:
        unseen = f1 * f1 / (2.0 * f2)
    else:
        unseen = f1 * max(f1 - 1, 0) / 2.0
    estimated = max(observed, ceil(observed + unseen))
    coverage = 1.0 - (f1 / max(sum(frequencies.values()), 1))
    confidence = round(max(0.0, min(1.0, coverage)), 3)
    return EntityPopulationEstimate(
        observed_entities=observed,
        estimated_entities=estimated,
        singletons=f1,
        doubletons=f2,
        sample_rows=sum(frequencies.values()),
        unseen_estimate=round(unseen, 3),
        confidence=confidence,
    )


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def infer_dataset_ordering(
    rows: list[dict[str, Any]], entity_field: str | None, timestamp_field: str | None
) -> DatasetOrdering:
    """Infer whether rows are time ordered, entity grouped, or effectively random."""
    if len(rows) < 4:
        return DatasetOrdering.UNKNOWN
    if timestamp_field:
        times = [_parse_time(row.get(timestamp_field)) for row in rows]
        comparable = [(a, b) for a, b in zip(times, times[1:]) if a and b]
        if comparable:
            ascending = sum(a <= b for a, b in comparable) / len(comparable)
            descending = sum(a >= b for a, b in comparable) / len(comparable)
            if ascending >= 0.9:
                return DatasetOrdering.TIME_ASCENDING
            if descending >= 0.9:
                return DatasetOrdering.TIME_DESCENDING
    if entity_field:
        entities = [str(row.get(entity_field)) for row in rows if row.get(entity_field) not in (None, "")]
        if len(entities) >= 4:
            adjacent_same = sum(a == b for a, b in zip(entities, entities[1:])) / (len(entities) - 1)
            if adjacent_same >= 0.6:
                return DatasetOrdering.ENTITY_GROUPED
            distinct = len(set(entities))
            if distinct > 1 and adjacent_same <= 0.2:
                return DatasetOrdering.EFFECTIVELY_RANDOM
    return DatasetOrdering.UNKNOWN


def build_retrieval_plan(
    model: ObservationModel,
    rows: list[dict[str, Any]],
    *,
    target_observations_per_entity: int = 50,
    max_import_rows: int = 100000,
) -> tuple[EntityPopulationEstimate, RetrievalPlan]:
    """Size final retrieval from estimated entities and dimensional row density."""
    entity_field = model.entity_fields[0] if model.entity_fields else None
    timestamp_field = model.timestamp_fields[0] if model.timestamp_fields else None
    population = estimate_entity_population(rows, entity_field)
    ordering = infer_dataset_ordering(rows, entity_field, timestamp_field)
    metric_multiplier = max(1, _distinct_values(rows, model.metric_dimension_fields))
    observation_multiplier = max(1, _distinct_values(rows, model.observation_dimension_fields))
    dimension_multiplier = max(1, metric_multiplier * observation_multiplier)
    estimated_entities = max(1, population.estimated_entities)
    target_rows = min(
        max_import_rows,
        estimated_entities * max(1, target_observations_per_entity) * dimension_multiplier,
    )
    per_entity = max(1, ceil(target_rows / estimated_entities))
    return population, RetrievalPlan(
        ordering=ordering,
        estimated_entities=estimated_entities,
        target_observations_per_entity=max(1, target_observations_per_entity),
        dimension_multiplier=dimension_multiplier,
        target_rows=target_rows,
        entity_limit=estimated_entities,
        observations_per_entity=per_entity,
    )


async def async_analyze_dataset(
    provider: OpenDataProvider,
    dataset: OpenDataDataset,
    *,
    initial_limit: int = 200,
    entity_limit: int = 20,
    sample_stages: tuple[int, ...] = _DEFAULT_SAMPLE_STAGES,
    target_observations_per_entity: int = 50,
    max_import_rows: int = 100000,
) -> DatasetAnalysis:
    """Analyze adaptively, estimate population, then retrieve representative history."""
    stages = tuple(sorted({max(1, int(value)) for value in sample_stages}))
    if not stages:
        raise ValueError("At least one adaptive sampling stage is required")

    first_limit = max(initial_limit, stages[0])
    initial_rows = await provider.async_sample_rows(
        dataset.dataset_id, dataset.resource_id, limit=first_limit
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
        growth = _growth(previous_signature, signature) if previous_signature else 1.0
        reports.append(SamplingStageReport(
            requested_rows=requested_rows,
            retrieved_rows=len(rows),
            entity_count=signature[0],
            metric_value_count=signature[1],
            observation_dimension_value_count=signature[2],
            shape=model.shape.value,
            confidence=model.confidence,
            structural_growth=round(growth, 3),
        ))
        if len(sampled) < requested_rows:
            converged = True
            stopped_reason = "provider_exhausted"
            break
        if index + 1 >= min(_MINIMUM_STAGES, len(stages)) and not _needs_deep_sample(
            model, growth, len(sampled), requested_rows
        ):
            converged = True
            stopped_reason = "structural_convergence"
            break
        previous_signature = signature

    semantic_model = analyze_observations(dataset, rows)
    population, plan = build_retrieval_plan(
        semantic_model,
        rows,
        target_observations_per_entity=target_observations_per_entity,
        max_import_rows=max_import_rows,
    )
    imported = await provider.async_sample_observations(
        dataset.dataset_id,
        dataset.resource_id,
        entity_field=semantic_model.entity_fields[0] if semantic_model.entity_fields else initial_structure.identity_field,
        timestamp_field=semantic_model.timestamp_fields[0] if semantic_model.timestamp_fields else initial_structure.timestamp_field,
        entity_limit=plan.entity_limit,
        observations_per_entity=plan.observations_per_entity,
    )
    rows = _merge_rows(rows, imported)
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
            entity_population=population,
            retrieval_plan=plan,
            imported_row_count=len(imported),
        ),
    )
