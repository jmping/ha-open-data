"""Provider-neutral dataset profiling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .field_semantics import FieldKind, FieldSemantic, classify_fields


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    """Inferred structural profile for one dataset."""

    fields: tuple[FieldSemantic, ...]
    timestamp: str | None = None
    latitude: str | None = None
    longitude: str | None = None
    identifier: str | None = None
    geometry: str | None = None
    measures: tuple[str, ...] = ()
    text_fields: tuple[str, ...] = ()


def build_dataset_profile(
    fields: Iterable[tuple[str, str | None, str | None]],
) -> DatasetProfile:
    """Build an immutable profile from normalized field descriptors."""
    semantics = classify_fields(fields)

    def first(kind: FieldKind) -> str | None:
        return next((item.name for item in semantics if item.kind is kind), None)

    return DatasetProfile(
        fields=semantics,
        timestamp=first(FieldKind.TIMESTAMP),
        latitude=first(FieldKind.LATITUDE),
        longitude=first(FieldKind.LONGITUDE),
        identifier=first(FieldKind.IDENTIFIER),
        geometry=first(FieldKind.GEOMETRY),
        measures=tuple(item.name for item in semantics if item.kind is FieldKind.MEASURE),
        text_fields=tuple(item.name for item in semantics if item.kind is FieldKind.TEXT),
    )
