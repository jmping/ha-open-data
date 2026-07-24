"""Build bounded observation evidence for dataset inspection and review."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from .analyzer import analyze_dataset, dataset_explorer_summary
from .models import OpenDataDataset
from .observation_sampling import (
    infer_functional_dependencies,
    stratify_observation_rows,
)


def build_dataset_inspection_evidence(
    dataset: OpenDataDataset,
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    sample_limit: int = 100,
) -> dict[str, Any]:
    """Return explorer analysis plus bounded sample and relationship evidence."""
    materialized = [dict(row) for row in candidate_rows]
    preliminary = analyze_dataset(dataset, materialized)
    identity_fields = (
        (preliminary.identity_field,) if preliminary.identity_field is not None else ()
    )
    sample = stratify_observation_rows(
        materialized,
        timestamp_field=preliminary.timestamp_field,
        identity_fields=identity_fields,
        limit=sample_limit,
    )
    rows = [dict(row) for row in sample.rows]
    analysis = dataset_explorer_summary(dataset, rows)
    dimensions = analysis.get("dimensions", {})
    relationship_fields = tuple(
        dict.fromkeys(
            field
            for group in ("identity", "display", "location", "hierarchy")
            for field in dimensions.get(group, ())
        )
    )
    relationships = infer_functional_dependencies(
        rows,
        fields=relationship_fields,
    )
    analysis["sampling_evidence"] = sample.evidence.as_dict()
    analysis["historical_relationships"] = [
        asdict(relationship) for relationship in relationships
    ]
    return analysis
