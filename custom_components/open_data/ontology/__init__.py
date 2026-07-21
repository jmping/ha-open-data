"""Declarative municipal-data ontology and deterministic profile matching."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import re
from typing import Any

from ..models import OpenDataDataset, OpenDataField

_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """One canonical municipal metric and its known field aliases."""

    metric_id: str
    aliases: frozenset[str]
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProfileDefinition:
    """A declarative dataset archetype."""

    profile_id: str
    title: str
    metadata_terms: tuple[str, ...]
    core_metrics: tuple[str, ...]
    support_metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """Auditable mapping from a source field to a canonical metric."""

    source_field: str
    canonical_metric: str
    mapping_method: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    """Best deterministic profile match for a dataset."""

    profile_id: str
    title: str
    confidence: float
    mappings: tuple[FieldMapping, ...]
    matched_core: tuple[str, ...]
    matched_support: tuple[str, ...]
    reasons: tuple[str, ...]


def normalize_identifier(value: str) -> str:
    """Normalize field names and aliases for deterministic comparison."""
    return _NORMALIZE_PATTERN.sub("_", value.casefold()).strip("_")


@lru_cache(maxsize=1)
def _load_ontology() -> tuple[dict[str, MetricDefinition], tuple[ProfileDefinition, ...]]:
    """Load and validate the bundled JSON ontology once per process."""
    ontology_path = files(__package__).joinpath("profiles.json")
    payload = json.loads(ontology_path.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("Unsupported open-data ontology version")

    metrics: dict[str, MetricDefinition] = {}
    for metric_id, raw in payload.get("metrics", {}).items():
        aliases = {
            normalize_identifier(metric_id),
            *(normalize_identifier(item) for item in raw.get("aliases", [])),
        }
        metadata = {key: value for key, value in raw.items() if key != "aliases"}
        metrics[metric_id] = MetricDefinition(
            metric_id=metric_id,
            aliases=frozenset(aliases),
            metadata=metadata,
        )

    profiles = tuple(
        ProfileDefinition(
            profile_id=item["id"],
            title=item["title"],
            metadata_terms=tuple(term.casefold() for term in item.get("metadata_terms", [])),
            core_metrics=tuple(item.get("core", [])),
            support_metrics=tuple(item.get("support", [])),
        )
        for item in payload.get("profiles", [])
    )
    return metrics, profiles


def metric_definitions() -> dict[str, MetricDefinition]:
    """Return the canonical metric registry."""
    return dict(_load_ontology()[0])


def profile_definitions() -> tuple[ProfileDefinition, ...]:
    """Return all bundled profile definitions."""
    return _load_ontology()[1]


def _field_text(field: OpenDataField) -> tuple[str, ...]:
    return tuple(
        normalize_identifier(value)
        for value in (field.name, field.label, field.description or "")
        if value
    )


def map_fields(fields: tuple[OpenDataField, ...]) -> tuple[FieldMapping, ...]:
    """Map source fields to canonical metrics using exact normalized aliases."""
    metrics, _profiles = _load_ontology()
    mappings: list[FieldMapping] = []
    claimed_metrics: set[str] = set()

    for field in fields:
        candidates = _field_text(field)
        best: FieldMapping | None = None
        for metric in metrics.values():
            if metric.metric_id in claimed_metrics:
                continue
            confidence = 0.0
            if candidates and candidates[0] in metric.aliases:
                confidence = 1.0
            elif len(candidates) > 1 and candidates[1] in metric.aliases:
                confidence = 0.96
            elif any(candidate in metric.aliases for candidate in candidates[2:]):
                confidence = 0.88
            if confidence and (best is None or confidence > best.confidence):
                best = FieldMapping(
                    source_field=field.name,
                    canonical_metric=metric.metric_id,
                    mapping_method="synonym",
                    confidence=confidence,
                )
        if best is not None:
            mappings.append(best)
            claimed_metrics.add(best.canonical_metric)

    return tuple(mappings)


def _dataset_metadata_text(dataset: OpenDataDataset) -> str:
    values = [dataset.title, dataset.description or ""]
    for key in ("tags", "keywords", "organization", "publisher", "category"):
        value = dataset.raw.get(key)
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
    return " ".join(values).casefold()


def match_dataset_profile(dataset: OpenDataDataset) -> ProfileMatch | None:
    """Return the highest-confidence deterministic profile match."""
    _metrics, profiles = _load_ontology()
    mappings = map_fields(dataset.fields)
    mapped = {mapping.canonical_metric for mapping in mappings}
    metadata = _dataset_metadata_text(dataset)
    best: ProfileMatch | None = None

    for profile in profiles:
        matched_core = tuple(metric for metric in profile.core_metrics if metric in mapped)
        matched_support = tuple(metric for metric in profile.support_metrics if metric in mapped)
        metadata_hits = tuple(term for term in profile.metadata_terms if term in metadata)

        core_denominator = max(len(profile.core_metrics), 1)
        support_denominator = max(len(profile.support_metrics), 1)
        core_ratio = len(matched_core) / core_denominator
        support_ratio = len(matched_support) / support_denominator
        metadata_ratio = min(len(metadata_hits), 2) / 2

        if dataset.fields:
            confidence = min(1.0, 0.65 * core_ratio + 0.20 * support_ratio + 0.15 * metadata_ratio)
            if not matched_core:
                confidence *= 0.45
        else:
            confidence = 0.35 * metadata_ratio

        if confidence < 0.15:
            continue

        reasons = tuple(
            [*(f"metric:{item}" for item in matched_core), *(f"term:{item}" for item in metadata_hits[:2])]
        )
        candidate = ProfileMatch(
            profile_id=profile.profile_id,
            title=profile.title,
            confidence=round(confidence, 3),
            mappings=tuple(
                mapping
                for mapping in mappings
                if mapping.canonical_metric in set(profile.core_metrics + profile.support_metrics)
            ),
            matched_core=matched_core,
            matched_support=matched_support,
            reasons=reasons,
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate

    return best


def mapping_provenance(dataset: OpenDataDataset) -> list[dict[str, Any]]:
    """Return service-safe mapping provenance for diagnostics and future review."""
    match = match_dataset_profile(dataset)
    if match is None:
        return []
    return [
        {
            "profile": match.profile_id,
            "canonical_metric": mapping.canonical_metric,
            "source_field": mapping.source_field,
            "mapping_method": mapping.mapping_method,
            "confidence": mapping.confidence,
        }
        for mapping in match.mappings
    ]
