"""Infer location-related fields without provider coupling."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

_LOCATION_NAMES = {
    "station_name": "station",
    "site_name": "station",
    "location_name": "location",
    "city": "municipality",
    "municipality": "municipality",
    "county": "region",
    "region": "region",
    "state": "region",
    "province": "region",
    "country": "country",
}


@dataclass(frozen=True, slots=True)
class LocationCandidate:
    field: str
    role: str
    confidence: int


def infer_location_fields(
    fields: Iterable[tuple[str, str | None, str | None]],
) -> tuple[LocationCandidate, ...]:
    """Return recognized location fields in deterministic confidence order."""
    candidates: list[LocationCandidate] = []
    for name, label, _data_type in fields:
        normalized = {_normalize(name), _normalize(label or "")}
        for alias, role in _LOCATION_NAMES.items():
            if alias in normalized:
                candidates.append(LocationCandidate(name, role, 85 if _normalize(name) == alias else 70))
                break
    return tuple(sorted(candidates, key=lambda item: (-item.confidence, item.field.casefold())))


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
