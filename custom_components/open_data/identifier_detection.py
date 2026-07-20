"""Provider-neutral identifier field detection."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_STRONG = {"id", "uuid", "guid", "station_id", "sensor_id", "feature_id", "record_id"}
_WEAK = {"code", "identifier", "station_code", "site_code"}
_REJECT = {"latitude", "longitude", "timestamp", "date", "time", "temperature"}


@dataclass(frozen=True, slots=True)
class IdentifierCandidate:
    """One identifier candidate."""

    name: str
    score: int
    reasons: tuple[str, ...]


def score_identifier_field(name: str, label: str | None = None, data_type: str | None = None) -> IdentifierCandidate:
    """Score a field as a stable row or station identifier."""
    values = {_normalize(name), _normalize(label or "")}
    score = 0
    reasons: list[str] = []
    if values & _REJECT:
        return IdentifierCandidate(name, 0, ("semantic false positive",))
    if values & _STRONG:
        score += 80
        reasons.append("strong identifier name")
    elif values & _WEAK:
        score += 55
        reasons.append("identifier-like name")
    normalized_type = _normalize(data_type or "")
    if normalized_type in {"uuid", "guid"}:
        score += 20
        reasons.append("identifier type")
    return IdentifierCandidate(name, min(score, 100), tuple(reasons))


def rank_identifier_fields(fields: Iterable[tuple[str, str | None, str | None]]) -> tuple[IdentifierCandidate, ...]:
    """Rank identifier candidates deterministically."""
    candidates = [candidate for name, label, data_type in fields if (candidate := score_identifier_field(name, label, data_type)).score]
    return tuple(sorted(candidates, key=lambda item: (-item.score, item.name.casefold())))


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
