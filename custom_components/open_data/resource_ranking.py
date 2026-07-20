"""Provider-neutral resource ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

_FORMAT_SCORES = {"csv": 30, "json": 25, "geojson": 25, "api": 20, "parquet": 35}


@dataclass(frozen=True, slots=True)
class ResourceDescriptor:
    """Minimal normalized resource facts for ranking."""

    resource_id: str
    format: str | None = None
    queryable: bool = False
    schema_rich: bool = False
    spatial: bool = False
    modified: datetime | None = None


@dataclass(frozen=True, slots=True)
class RankedResource:
    """Resource ranking result."""

    resource: ResourceDescriptor
    score: int
    reasons: tuple[str, ...]


def rank_resources(resources: Iterable[ResourceDescriptor]) -> tuple[RankedResource, ...]:
    """Rank resources by reusable provider-neutral signals."""
    ranked: list[RankedResource] = []
    for resource in resources:
        score = _FORMAT_SCORES.get((resource.format or "").casefold(), 0)
        reasons: list[str] = []
        if score:
            reasons.append("preferred format")
        if resource.queryable:
            score += 35
            reasons.append("queryable")
        if resource.schema_rich:
            score += 20
            reasons.append("schema metadata")
        if resource.spatial:
            score += 10
            reasons.append("spatial support")
        ranked.append(RankedResource(resource, score, tuple(reasons)))
    return tuple(sorted(ranked, key=lambda item: (-item.score, -(item.resource.modified.timestamp() if item.resource.modified else float("-inf")), item.resource.resource_id.casefold())))
