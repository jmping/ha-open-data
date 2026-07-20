"""Provider-neutral semantic field classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable

from .coordinate_detection import detect_coordinate_pair
from .geometry_detection import rank_geometry_fields
from .identifier_detection import rank_identifier_fields
from .timestamp_detection import rank_timestamp_fields


class FieldKind(StrEnum):
    """Supported inferred field semantics."""

    TIMESTAMP = "timestamp"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    IDENTIFIER = "identifier"
    GEOMETRY = "geometry"
    MEASURE = "measure"
    TEXT = "text"


@dataclass(frozen=True, slots=True)
class FieldSemantic:
    """Semantic classification for one field."""

    name: str
    kind: FieldKind
    confidence: int
    reasons: tuple[str, ...] = ()
    paired_with: str | None = None


def classify_fields(fields: Iterable[tuple[str, str | None, str | None]]) -> tuple[FieldSemantic, ...]:
    """Classify normalized field descriptors without provider coupling."""
    descriptors = tuple(fields)
    classified: dict[str, FieldSemantic] = {}
    timestamps = rank_timestamp_fields(descriptors)
    if timestamps:
        item = timestamps[0]
        classified[item.name] = FieldSemantic(item.name, FieldKind.TIMESTAMP, min(item.score, 100), item.reasons)
    pair = detect_coordinate_pair(descriptors)
    if pair:
        classified[pair.latitude.name] = FieldSemantic(pair.latitude.name, FieldKind.LATITUDE, pair.latitude.score, pair.latitude.reasons, pair.longitude.name)
        classified[pair.longitude.name] = FieldSemantic(pair.longitude.name, FieldKind.LONGITUDE, pair.longitude.score, pair.longitude.reasons, pair.latitude.name)
    identifiers = rank_identifier_fields(descriptors)
    if identifiers and identifiers[0].name not in classified:
        item = identifiers[0]
        classified[item.name] = FieldSemantic(item.name, FieldKind.IDENTIFIER, item.score, item.reasons)
    geometries = rank_geometry_fields(descriptors)
    if geometries and geometries[0].name not in classified:
        item = geometries[0]
        classified[item.name] = FieldSemantic(item.name, FieldKind.GEOMETRY, item.score, item.reasons)
    numeric_types = {"number", "numeric", "float", "double", "decimal", "integer", "int", "real"}
    for name, _label, data_type in descriptors:
        if name in classified:
            continue
        kind = FieldKind.MEASURE if (data_type or "").casefold() in numeric_types else FieldKind.TEXT
        confidence = 55 if kind is FieldKind.MEASURE else 30
        classified[name] = FieldSemantic(name, kind, confidence, ("numeric type",) if kind is FieldKind.MEASURE else ())
    return tuple(classified[name] for name, *_ in descriptors)
