"""Provider-independent field role classification for Home Assistant entities."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping


_TIME_COMPONENTS = {
    "year", "month", "day", "hour", "minute", "second", "quarter", "week",
    "weekday", "date", "time", "timestamp", "datetime", "observed_at",
    "observation_time", "sample_date", "sample_time", "created_at", "updated_at",
    "created_date", "closed_date", "due_date", "resolution_action_updated_date",
    "date_collected", "received_date", "recorded_at", "measurement_time",
}
_CONTEXT_TERMS = (
    "agency", "vendor", "owner", "program", "project", "source", "status",
    "station", "site", "location", "beach", "waterbody", "water_body", "river",
    "lake", "county", "city", "municipality", "township", "state", "region",
    "watershed", "basin", "district", "precinct", "ward", "borough", "address",
    "street", "cross_street", "intersection", "community_board", "zip", "zipcode",
    "latitude", "longitude", "lat", "lon", "lng", "geometry", "sample_no",
    "sample_number", "sample_id", "kit_id", "unique_key", "permit", "facility",
    "descriptor", "complaint_type", "resolution", "name", "label", "id",
)
_MEASUREMENT_TERMS = (
    "temperature", "humidity", "pressure", "concentration", "level", "height",
    "depth", "flow", "speed", "velocity", "rain", "precip", "wind", "battery",
    "voltage", "current", "power", "energy", "count", "total", "sum", "average",
    "mean", "median", "rate", "index", "score", "reading", "measurement", "value",
    "lead", "copper", "turbidity", "conductivity", "oxygen", "ph", "tonnage",
    "tons", "weight", "volume", "distance", "duration", "occupancy", "capacity",
    "pfas", "pfoa", "pfos", "pfna", "pfba", "pfhpa", "pfhxa", "pfhxs", "pfpea",
    "pfteda", "6_2_fts", "wave",
)
_NON_MEASUREMENT_VALUES = {
    "not detected", "not measured", "unknown", "n/a", "na", "none", "null", "",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str) or value.strip().casefold() in _NON_MEASUREMENT_VALUES:
        return False
    try:
        float(value.strip())
        return True
    except ValueError:
        return False


@dataclass(slots=True, frozen=True)
class FieldRoles:
    """Fields split into entity-producing metrics and descriptive context."""

    metric_fields: tuple[str, ...]
    context_fields: tuple[str, ...]
    time_fields: tuple[str, ...]


def classify_field_roles(
    field_names: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
    *,
    configured_metrics: Iterable[str] = (),
    structural_fields: Iterable[str] = (),
    timestamp_fields: Iterable[str] = (),
    ignored_fields: Iterable[str] = (),
) -> FieldRoles:
    """Classify fields conservatively, preserving non-metrics as context.

    Explicit ontology/configuration metrics win. Otherwise numeric values and
    measurement vocabulary are used together. Time components and structural
    identifiers never become sensors merely because they contain numbers.
    """
    fields = tuple(dict.fromkeys(field_names))
    ignored = set(ignored_fields)
    structural = set(structural_fields)
    configured = set(configured_metrics) - ignored
    explicit_time = set(timestamp_fields)
    row_list = list(rows)

    time_fields: list[str] = []
    metrics: list[str] = []
    context: list[str] = []

    for field in fields:
        if field in ignored:
            continue
        norm = _norm(field)
        is_time = field in explicit_time or norm in _TIME_COMPONENTS
        if is_time:
            time_fields.append(field)
            continue
        if field in configured:
            metrics.append(field)
            continue

        values = [row.get(field) for row in row_list if row.get(field) not in (None, "")]
        numeric_ratio = (
            sum(_is_number(value) for value in values) / len(values) if values else 0.0
        )
        measurement_name = any(term in norm for term in _MEASUREMENT_TERMS)
        context_name = field in structural or any(term in norm for term in _CONTEXT_TERMS)

        if measurement_name and numeric_ratio >= 0.2 and not context_name:
            metrics.append(field)
        elif numeric_ratio >= 0.8 and not context_name:
            metrics.append(field)
        else:
            context.append(field)

    return FieldRoles(tuple(metrics), tuple(context), tuple(time_fields))


def context_attributes(
    values: Mapping[str, Any], context_fields: Iterable[str], *, limit: int = 30
) -> dict[str, Any]:
    """Return bounded, Home Assistant-safe descriptive attributes."""
    attributes: dict[str, Any] = {}
    for field in context_fields:
        value = values.get(field)
        if value in (None, ""):
            continue
        if isinstance(value, (str, int, float, bool)):
            attributes[field] = value
        else:
            attributes[field] = str(value)[:255]
        if len(attributes) >= limit:
            break
    return attributes
