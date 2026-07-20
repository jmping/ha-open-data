"""Provider-independent discovery and ranking for public datasets."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .models import OpenDataDataset

_ENVIRONMENT_TERMS: dict[str, int] = {
    "air quality": 35,
    "weather": 30,
    "temperature": 24,
    "humidity": 22,
    "pm2.5": 35,
    "pm25": 35,
    "pm10": 30,
    "aqi": 35,
    "ozone": 24,
    "rainfall": 30,
    "precipitation": 28,
    "river": 22,
    "stream": 20,
    "water level": 24,
    "flood": 24,
    "wind": 20,
    "climate": 18,
    "solar": 18,
    "energy": 14,
    "sensor": 16,
    "hourly": 14,
    "real time": 18,
    "realtime": 18,
}

_LOW_VALUE_TERMS: dict[str, int] = {
    "payroll": -35,
    "budget": -20,
    "procurement": -18,
    "meeting minutes": -30,
    "pdf": -18,
    "archive": -15,
}

_FIELD_TERMS: dict[str, int] = {
    "timestamp": 12,
    "date": 6,
    "time": 6,
    "station": 10,
    "latitude": 8,
    "longitude": 8,
    "temperature": 16,
    "humidity": 16,
    "pm25": 20,
    "pm2_5": 20,
    "pm10": 18,
    "aqi": 20,
    "rain": 14,
    "precip": 14,
    "wind": 12,
}


@dataclass(slots=True, frozen=True)
class DatasetCandidate:
    """A normalized dataset with a discovery score and explanation."""

    dataset: OpenDataDataset
    score: int
    reasons: tuple[str, ...]


def _text_from_raw(raw: dict[str, Any]) -> str:
    """Extract useful provider metadata without coupling to one provider."""
    values: list[str] = []
    for key in ("tags", "keywords", "organization", "publisher", "frequency"):
        value = raw.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, dict):
                    values.extend(
                        str(item[name])
                        for name in ("name", "display_name", "title")
                        if item.get(name)
                    )
        elif isinstance(value, dict):
            values.extend(str(item) for item in value.values() if isinstance(item, str))
    return " ".join(values)


def score_dataset(dataset: OpenDataDataset) -> DatasetCandidate:
    """Score a dataset for Home Assistant environmental observability."""
    title = dataset.title.lower()
    description = (dataset.description or "").lower()
    metadata = _text_from_raw(dataset.raw).lower()
    searchable = re.sub(r"[^a-z0-9.]+", " ", f"{title} {description} {metadata}")

    score = 0
    reasons: list[str] = []
    for term, weight in _ENVIRONMENT_TERMS.items():
        if term in searchable:
            score += weight
            reasons.append(term)
    for term, weight in _LOW_VALUE_TERMS.items():
        if term in searchable:
            score += weight
            reasons.append(term)

    if dataset.resource_id:
        score += 15
        reasons.append("queryable resource")
    if dataset.fields:
        score += 10
        reasons.append("schema available")
        field_names = " ".join(field.name.lower() for field in dataset.fields)
        for term, weight in _FIELD_TERMS.items():
            if term in field_names:
                score += weight
                reasons.append(f"field:{term}")

    return DatasetCandidate(dataset=dataset, score=score, reasons=tuple(dict.fromkeys(reasons)))


def rank_datasets(
    datasets: Iterable[OpenDataDataset], *, minimum_score: int = 0
) -> list[DatasetCandidate]:
    """Return deterministic, highest-value-first discovery results."""
    candidates = (score_dataset(dataset) for dataset in datasets)
    return sorted(
        (candidate for candidate in candidates if candidate.score >= minimum_score),
        key=lambda candidate: (-candidate.score, candidate.dataset.title.casefold()),
    )
