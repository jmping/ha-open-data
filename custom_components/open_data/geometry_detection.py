"""Provider-neutral geometry field detection."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_NAMES = {"geometry", "geom", "shape", "the_geom", "geojson", "wkt"}
_TYPES = {"geometry", "geography", "geojson", "wkt", "point", "linestring", "polygon", "multipolygon"}


@dataclass(frozen=True, slots=True)
class GeometryCandidate:
    """One geometry field candidate."""

    name: str
    score: int
    reasons: tuple[str, ...]


def score_geometry_field(name: str, label: str | None = None, data_type: str | None = None) -> GeometryCandidate:
    """Score one field as encoded geometry."""
    values = {_normalize(name), _normalize(label or "")}
    normalized_type = _normalize(data_type or "")
    score = 0
    reasons: list[str] = []
    if values & _NAMES:
        score += 65
        reasons.append("geometry-like name")
    if normalized_type in _TYPES:
        score += 35
        reasons.append("geometry type")
    return GeometryCandidate(name, min(score, 100), tuple(reasons))


def rank_geometry_fields(fields: Iterable[tuple[str, str | None, str | None]]) -> tuple[GeometryCandidate, ...]:
    """Rank geometry candidates deterministically."""
    candidates = [candidate for name, label, data_type in fields if (candidate := score_geometry_field(name, label, data_type)).score]
    return tuple(sorted(candidates, key=lambda item: (-item.score, item.name.casefold())))


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
