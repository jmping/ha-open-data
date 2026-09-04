"""Ordering-aware bounded sampling for heterogeneous public datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .observation_sampling import ObservationSample, stratify_observation_rows
from .refresh_policy import parse_timestamp


@dataclass(frozen=True, slots=True)
class SourceOrderingProfile:
    """Evidence about the physical ordering of one provider sample window."""

    mode: str
    timestamp_coverage: float
    temporal_monotonicity: float
    temporal_direction: str | None
    entity_run_ratio: float
    distinct_entities: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _entity_value(row: Mapping[str, Any], identity_fields: Sequence[str]) -> str | None:
    values = [
        str(row[field]).strip()
        for field in identity_fields
        if row.get(field) not in (None, "")
    ]
    return "|".join(values) if values else None


def profile_source_order(
    rows: Sequence[Mapping[str, Any]],
    *,
    timestamp_field: str | None,
    identity_fields: Sequence[str] = (),
) -> SourceOrderingProfile:
    """Classify a provider window as temporal, unit-clustered, or mixed.

    This deliberately describes physical response order rather than inferred data
    semantics. A source can therefore be unit-clustered even when every row also
    contains a perfectly usable timestamp.
    """
    materialized = list(rows)
    parsed = [
        parse_timestamp(row.get(timestamp_field)) if timestamp_field else None
        for row in materialized
    ]
    valid_count = sum(value is not None for value in parsed)
    timestamp_coverage = valid_count / max(len(materialized), 1)

    comparable: list[tuple[datetime, datetime]] = []
    for left, right in zip(parsed, parsed[1:]):
        if left is not None and right is not None:
            comparable.append((left, right))
    ascending = (
        sum(right >= left for left, right in comparable) / len(comparable)
        if comparable
        else 0.0
    )
    descending = (
        sum(right <= left for left, right in comparable) / len(comparable)
        if comparable
        else 0.0
    )
    temporal_monotonicity = max(ascending, descending)
    temporal_direction = None
    if comparable:
        temporal_direction = "ascending" if ascending >= descending else "descending"

    entities = [_entity_value(row, identity_fields) for row in materialized]
    valid_entities = [value for value in entities if value is not None]
    adjacent_entity_pairs = [
        (left, right)
        for left, right in zip(entities, entities[1:])
        if left is not None and right is not None
    ]
    entity_run_ratio = (
        sum(left == right for left, right in adjacent_entity_pairs)
        / len(adjacent_entity_pairs)
        if adjacent_entity_pairs
        else 0.0
    )
    distinct_entities = len(set(valid_entities))

    # Strong contiguous runs of the same observed unit are direct evidence of
    # unit-clustered physical order. A unit-clustered table can still appear
    # mostly monotonic in time because each unit's timestamps run forward before
    # the next unit begins; do not let that weak global monotonicity hide the runs.
    if (
        distinct_entities >= 2
        and entity_run_ratio >= 0.55
        and temporal_monotonicity < 0.98
    ):
        mode = "unit_clustered"
    elif timestamp_coverage >= 0.6 and temporal_monotonicity >= 0.85:
        mode = f"time_{temporal_direction}"
    elif distinct_entities >= 2 and entity_run_ratio >= 0.55:
        mode = "unit_clustered"
    else:
        mode = "mixed"

    return SourceOrderingProfile(
        mode=mode,
        timestamp_coverage=round(timestamp_coverage, 4),
        temporal_monotonicity=round(temporal_monotonicity, 4),
        temporal_direction=temporal_direction,
        entity_run_ratio=round(entity_run_ratio, 4),
        distinct_entities=distinct_entities,
    )


def merge_candidate_windows(
    physical_rows: Sequence[Mapping[str, Any]],
    recent_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Merge bounded provider windows while preserving first-seen row order."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_row in (*physical_rows, *recent_rows):
        row = dict(raw_row)
        key = repr(tuple(row.items()))
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def build_interpretation_sample(
    physical_rows: Sequence[Mapping[str, Any]],
    recent_rows: Sequence[Mapping[str, Any]],
    *,
    timestamp_field: str | None,
    identity_fields: Sequence[str] = (),
    limit: int = 100,
) -> tuple[ObservationSample, SourceOrderingProfile]:
    """Build a reproducible sample after determining physical source order."""
    ordering = profile_source_order(
        physical_rows,
        timestamp_field=timestamp_field,
        identity_fields=identity_fields,
    )
    merged = merge_candidate_windows(physical_rows, recent_rows)
    sample = stratify_observation_rows(
        merged,
        timestamp_field=timestamp_field,
        identity_fields=identity_fields,
        limit=limit,
    )
    return sample, ordering
