"""Provider-neutral sampling diagnostics and retrieval planning.

This module salvages the useful, pure-Python analysis ideas from the older
semantic-runtime branch without coupling them to provider execution or Home
Assistant entity creation. Runtime wiring can be added separately after live
validation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import ceil
from typing import Any, Iterable, Mapping


class DatasetOrdering(StrEnum):
    """Observed physical ordering of sampled source rows."""

    TIME_ASCENDING = "time_ascending"
    TIME_DESCENDING = "time_descending"
    ENTITY_GROUPED = "entity_grouped"
    EFFECTIVELY_RANDOM = "effectively_random"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class EntityPopulationEstimate:
    """Lower-bound estimate of an entity population from repeated sightings."""

    observed_entities: int
    estimated_entities: int
    singletons: int
    doubletons: int
    sample_rows: int
    unseen_estimate: float
    confidence: float


@dataclass(frozen=True, slots=True)
class RetrievalPlan:
    """Bounded row target for a future provider retrieval operation."""

    ordering: DatasetOrdering
    estimated_entities: int
    target_observations_per_entity: int
    dimension_multiplier: int
    target_rows: int
    observations_per_entity: int


def estimate_entity_population(
    rows: Iterable[Mapping[str, Any]], entity_field: str | None
) -> EntityPopulationEstimate:
    """Estimate entity population using the bias-corrected Chao1 lower bound."""

    row_list = list(rows)
    if not entity_field:
        return EntityPopulationEstimate(0, 0, 0, 0, len(row_list), 0.0, 0.0)

    frequencies = Counter(
        str(row[entity_field])
        for row in row_list
        if row.get(entity_field) not in (None, "")
    )
    observed = len(frequencies)
    sample_rows = sum(frequencies.values())
    singletons = sum(count == 1 for count in frequencies.values())
    doubletons = sum(count == 2 for count in frequencies.values())

    if observed == 0:
        unseen = 0.0
    elif doubletons:
        unseen = singletons * singletons / (2.0 * doubletons)
    else:
        unseen = singletons * max(singletons - 1, 0) / 2.0

    estimated = max(observed, ceil(observed + unseen))
    coverage = 1.0 - singletons / max(sample_rows, 1)
    return EntityPopulationEstimate(
        observed_entities=observed,
        estimated_entities=estimated,
        singletons=singletons,
        doubletons=doubletons,
        sample_rows=sample_rows,
        unseen_estimate=round(unseen, 3),
        confidence=round(max(0.0, min(1.0, coverage)), 3),
    )


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def infer_dataset_ordering(
    rows: Iterable[Mapping[str, Any]],
    entity_field: str | None,
    timestamp_field: str | None,
) -> DatasetOrdering:
    """Infer time ordering or entity grouping from a bounded row sample."""

    row_list = list(rows)
    if len(row_list) < 4:
        return DatasetOrdering.UNKNOWN

    if timestamp_field:
        times = [_parse_time(row.get(timestamp_field)) for row in row_list]
        comparable = [(left, right) for left, right in zip(times, times[1:]) if left and right]
        if comparable:
            ascending = sum(left <= right for left, right in comparable) / len(comparable)
            descending = sum(left >= right for left, right in comparable) / len(comparable)
            if ascending >= 0.9:
                return DatasetOrdering.TIME_ASCENDING
            if descending >= 0.9:
                return DatasetOrdering.TIME_DESCENDING

    if entity_field:
        entities = [
            str(row[entity_field])
            for row in row_list
            if row.get(entity_field) not in (None, "")
        ]
        if len(entities) >= 4:
            adjacent_same = sum(
                left == right for left, right in zip(entities, entities[1:])
            ) / (len(entities) - 1)
            if adjacent_same >= 0.6:
                return DatasetOrdering.ENTITY_GROUPED
            if len(set(entities)) > 1 and adjacent_same <= 0.2:
                return DatasetOrdering.EFFECTIVELY_RANDOM

    return DatasetOrdering.UNKNOWN


def distinct_value_count(
    rows: Iterable[Mapping[str, Any]], fields: Iterable[str]
) -> int:
    """Return the summed distinct-value count for bounded dimension fields."""

    row_list = list(rows)
    return sum(
        len({str(row[field]) for row in row_list if row.get(field) not in (None, "")})
        for field in fields
    )


def build_retrieval_plan(
    rows: Iterable[Mapping[str, Any]],
    *,
    entity_field: str | None,
    timestamp_field: str | None,
    metric_dimension_fields: Iterable[str] = (),
    observation_dimension_fields: Iterable[str] = (),
    target_observations_per_entity: int = 50,
    max_import_rows: int = 100_000,
) -> tuple[EntityPopulationEstimate, RetrievalPlan]:
    """Size a bounded retrieval using population and dimensional row density."""

    row_list = list(rows)
    population = estimate_entity_population(row_list, entity_field)
    ordering = infer_dataset_ordering(row_list, entity_field, timestamp_field)
    metric_multiplier = max(1, distinct_value_count(row_list, metric_dimension_fields))
    observation_multiplier = max(
        1, distinct_value_count(row_list, observation_dimension_fields)
    )
    dimension_multiplier = max(1, metric_multiplier * observation_multiplier)
    estimated_entities = max(1, population.estimated_entities)
    target_per_entity = max(1, target_observations_per_entity)
    target_rows = min(
        max(1, max_import_rows),
        estimated_entities * target_per_entity * dimension_multiplier,
    )
    return population, RetrievalPlan(
        ordering=ordering,
        estimated_entities=estimated_entities,
        target_observations_per_entity=target_per_entity,
        dimension_multiplier=dimension_multiplier,
        target_rows=target_rows,
        observations_per_entity=max(1, ceil(target_rows / estimated_entities)),
    )
