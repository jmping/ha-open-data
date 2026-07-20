"""Deterministic resource scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

_DATASTORE_SCORE = 100
_ACTIVE_SCORE = 20
_FORMAT_SCORES = {
    "csv": 12,
    "json": 10,
    "geojson": 10,
    "api": 8,
}


@dataclass(frozen=True, slots=True)
class ResourceScore:
    """Score and explanation for a provider resource."""

    score: int
    reasons: tuple[str, ...]
    modified: datetime | None = None


def score_resource(resource: dict[str, Any]) -> ResourceScore:
    """Return a deterministic suitability score for a CKAN resource."""
    score = 0
    reasons: list[str] = []

    if resource.get("datastore_active") is True:
        score += _DATASTORE_SCORE
        reasons.append("DataStore enabled")

    state = str(resource.get("state", "active")).casefold()
    if state == "active":
        score += _ACTIVE_SCORE
        reasons.append("active")
    else:
        score -= _ACTIVE_SCORE
        reasons.append(f"state is {state or 'unknown'}")

    resource_format = str(resource.get("format", "")).strip().casefold()
    format_score = _FORMAT_SCORES.get(resource_format, 0)
    if format_score:
        score += format_score
        reasons.append(f"{resource_format.upper()} format")

    modified = _parse_datetime(
        resource.get("last_modified") or resource.get("metadata_modified")
    )
    if modified is not None:
        reasons.append("has modification timestamp")

    return ResourceScore(score=score, reasons=tuple(reasons), modified=modified)


def choose_best_resource(
    resources: Iterable[dict[str, Any]],
) -> dict[str, Any] | None:
    """Choose the highest-scoring active DataStore resource.

    Modification time and original input order provide deterministic tie-breaks.
    """
    eligible = [
        resource
        for resource in resources
        if resource.get("datastore_active") is True
        and str(resource.get("state", "active")).casefold() == "active"
    ]
    if not eligible:
        return None

    ranked = sorted(
        enumerate(eligible),
        key=lambda item: _ranking_key(item[1], item[0]),
        reverse=True,
    )
    return ranked[0][1]


def _ranking_key(resource: dict[str, Any], index: int) -> tuple[int, float, int]:
    result = score_resource(resource)
    modified = result.modified.timestamp() if result.modified else float("-inf")
    return result.score, modified, -index


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
