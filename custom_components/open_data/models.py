"""Normalized provider-independent data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class OpenDataField:
    """One dataset field."""

    name: str
    label: str
    data_type: str = "string"
    description: str | None = None


@dataclass(slots=True, frozen=True)
class OpenDataDataset:
    """Normalized dataset metadata."""

    dataset_id: str
    title: str
    description: str | None = None
    resource_id: str | None = None
    fields: tuple[OpenDataField, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(slots=True, frozen=True)
class SemanticObservation:
    """Latest value for one stable unit and logical measurement stream."""

    stream_id: str
    unit_id: str | None
    metric: str
    source_field: str
    value: Any
    timestamp: str | None = None
    record_id: str | None = None
    record_label: str | None = None
    source_row: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(slots=True, frozen=True)
class OpenDataSnapshot:
    """Latest normalized dataset state for one or more selected records."""

    dataset: OpenDataDataset
    values: dict[str, Any]
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    record_labels: dict[str, str] = field(default_factory=dict)
    observations: dict[str, SemanticObservation] = field(default_factory=dict)
