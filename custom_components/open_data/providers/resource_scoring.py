"""Deterministic resource scoring helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

_DATASTORE_SCORE = 100
_ACTIVE_SCORE = 20
_FORMAT_SCORES = {
    "csv": 12,
    "text/csv": 12,
    "json": 10,
    "application/json": 10,
    "geojson": 10,
    "application/geo+json": 10,
    "api": 8,
}


@dataclass(frozen=True, slots=True)
class ResourceScore:
    """Score and explanation for a provider resource."""

    score: int
    reasons: tuple[str, ...]
    modified: datetime | None = None


def score_resource(resource: Mapping[str, Any]) -> ResourceScore:
    """Return a deterministic suitability score for a CKAN resource."""
    score = 0
    reasons: list[str] = []

    if resource.get("datastore_active") is True:
        score += _DATASTORE_SCORE
        reasons.append("DataStore enabled")

    state = _normalized_text(resource.get("state"), default="active")
    if state == "active":
        score += _ACTIVE_SCORE
        reasons.append("active")
    else:
        score -= _ACTIVE_SCORE
        reasons.append(f"state is {state or 'unknown'}")

    resource_format = _normalized_text(resource.get("format"))
    format_score = _FORMAT_SCORES.get(resource_format, 0)
    if format_score:
        score += format_score
        reasons.append(f"{resource_format.upper()} format")

    modified = _first_datetime(
        resource.get("last_modified"),
        resource.get("metadata_modified"),
        resource.get("created"),
    )
    if modified is not None:
        reasons.append("has modification timestamp")

    return ResourceScore(score=score, reasons=tuple(reasons), modified=modified)


def choose_best_resource(
    resources: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Choose the highest-scoring active DataStore resource.

    Modification time and original input order provide deterministic tie-breaks.
    """
    eligible = [
        resource
        for resource in resources
        if resource.get("datastore_active") is True
        and _normalized_text(resource.get("state"), default="active") == "active"
    ]
    if not eligible:
        return None

    ranked = sorted(
        enumerate(eligible),
        key=lambda item: _ranking_key(item[1], item[0]),
        reverse=True,
    )
    return ranked[0][1]


def _ranking_key(
    resource: Mapping[str, Any], index: int
) -> tuple[int, float, int]:
    result = score_resource(resource)
    modified = result.modified.timestamp() if result.modified else float("-inf")
    return result.score, modified, -index


def _normalized_text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip().casefold()


def _first_datetime(*values: Any) -> datetime | None:
    for value in values:
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip()
    if normalized.endswith(("Z", "z")):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
