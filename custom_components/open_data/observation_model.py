"""Infer observation shapes and field behavior from bounded historical samples."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
import re
from typing import Any, Iterable

from .models import OpenDataDataset


class ObservationShape(StrEnum):
    """Supported physical layouts for observations."""

    UNKNOWN = "unknown"
    WIDE = "wide"
    LONG = "long"
    MULTI_DIMENSIONAL = "multi_dimensional"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class FieldStatistics:
    """Behavioral evidence calculated for one field."""

    field: str
    non_null_count: int
    distinct_count: int
    distinct_ratio: float
    numeric_ratio: float
    temporal_ratio: float
    repeated_ratio: float


@dataclass(frozen=True, slots=True)
class ObservationModel:
    """Provider-independent interpretation of a sampled observation table."""

    shape: ObservationShape
    confidence: float
    entity_fields: tuple[str, ...]
    timestamp_fields: tuple[str, ...]
    metric_fields: tuple[str, ...]
    metric_dimension_fields: tuple[str, ...]
    value_fields: tuple[str, ...]
    observation_dimension_fields: tuple[str, ...]
    unit_fields: tuple[str, ...]
    sample_row_count: int
    sampled_entity_count: int
    statistics: tuple[FieldStatistics, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a service-safe representation."""
        result = asdict(self)
        result["shape"] = self.shape.value
        return result


_METRIC_DIMENSION_TERMS = (
    "analyte",
    "parameter",
    "pollutant",
    "constituent",
    "characteristic",
    "metric",
    "measure",
    "measurement_type",
    "indicator",
    "variable",
    "test",
)
_VALUE_TERMS = (
    "value",
    "result",
    "reading",
    "measurement",
    "measured_value",
    "concentration",
    "amount",
    "quantity",
)
_UNIT_TERMS = ("unit", "units", "uom", "unit_of_measure", "measurement_unit")
_TIME_TERMS = (
    "timestamp",
    "datetime",
    "date_time",
    "observed",
    "observed_at",
    "sample_date",
    "date",
    "time",
)
_ENTITY_TERMS = (
    "station",
    "site",
    "sensor",
    "monitor",
    "well",
    "facility",
    "location",
    "asset",
    "beach",
    "gage",
    "gauge",
)
_OBSERVATION_DIMENSION_TERMS = (
    "depth",
    "height",
    "elevation",
    "level",
    "layer",
    "method",
    "medium",
    "matrix",
    "sample_type",
    "direction",
)


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _matches(name: str, terms: Iterable[str]) -> bool:
    normalized = _norm(name)
    return any(
        normalized == term
        or normalized.startswith(f"{term}_")
        or normalized.endswith(f"_{term}")
        for term in terms
    )


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return False
    try:
        float(value.replace(",", "").strip())
        return True
    except ValueError:
        return False


def _is_temporal(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip().replace("Z", "+00:00")
    if len(candidate) < 8:
        return False
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return bool(re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}.*", candidate))


def field_statistics(
    fields: Iterable[str], rows: list[dict[str, Any]]
) -> tuple[FieldStatistics, ...]:
    """Calculate bounded behavioral statistics used by shape inference."""
    output: list[FieldStatistics] = []
    for field in fields:
        values = [row.get(field) for row in rows if row.get(field) not in (None, "")]
        distinct = {str(value) for value in values}
        non_null = len(values)
        distinct_count = len(distinct)
        output.append(
            FieldStatistics(
                field=field,
                non_null_count=non_null,
                distinct_count=distinct_count,
                distinct_ratio=round(distinct_count / max(non_null, 1), 3),
                numeric_ratio=round(
                    sum(_is_number(value) for value in values) / max(non_null, 1), 3
                ),
                temporal_ratio=round(
                    sum(_is_temporal(value) for value in values) / max(non_null, 1), 3
                ),
                repeated_ratio=round(1.0 - distinct_count / max(non_null, 1), 3),
            )
        )
    return tuple(output)


def analyze_observations(
    dataset: OpenDataDataset, rows: list[dict[str, Any]] | None = None
) -> ObservationModel:
    """Infer wide, long, multi-dimensional, or event layout from history."""
    sample = rows or []
    fields = tuple(field.name for field in dataset.fields)
    stats = field_statistics(fields, sample)
    by_field = {item.field: item for item in stats}

    timestamps = tuple(
        field
        for field in fields
        if _matches(field, _TIME_TERMS) or by_field[field].temporal_ratio >= 0.7
    )
    units = tuple(field for field in fields if _matches(field, _UNIT_TERMS))

    metric_dimensions = tuple(
        field
        for field in fields
        if _matches(field, _METRIC_DIMENSION_TERMS)
        and 1 < by_field[field].distinct_count <= max(100, len(sample) // 2)
    )
    values = tuple(
        field
        for field in fields
        if _matches(field, _VALUE_TERMS) and by_field[field].numeric_ratio >= 0.5
    )

    # Named observation dimensions must be classified before generic repeated
    # dimensions. Values such as depth often repeat exactly like station IDs.
    observation_dimensions = tuple(
        field
        for field in fields
        if field not in timestamps
        and field not in metric_dimensions
        and field not in values
        and field not in units
        and _matches(field, _OBSERVATION_DIMENSION_TERMS)
        and by_field[field].distinct_count > 1
    )

    entity_fields = tuple(
        field
        for field in fields
        if field not in timestamps
        and field not in observation_dimensions
        and (
            _matches(field, _ENTITY_TERMS)
            or (
                1 < by_field[field].distinct_count < max(2, len(sample) // 2)
                and by_field[field].repeated_ratio >= 0.35
            )
        )
        and field not in metric_dimensions
        and field not in values
        and field not in units
    )

    excluded = {
        *entity_fields,
        *timestamps,
        *metric_dimensions,
        *values,
        *units,
        *observation_dimensions,
    }
    wide_metrics = tuple(
        field
        for field in fields
        if field not in excluded and by_field[field].numeric_ratio >= 0.8
    )

    if metric_dimensions and values:
        shape = (
            ObservationShape.MULTI_DIMENSIONAL
            if observation_dimensions
            else ObservationShape.LONG
        )
        confidence = 0.9
    elif timestamps and wide_metrics:
        shape = ObservationShape.WIDE
        confidence = 0.82 if entity_fields else 0.72
    elif timestamps:
        shape = ObservationShape.EVENT
        confidence = 0.65
    else:
        shape = ObservationShape.UNKNOWN
        confidence = 0.35

    primary_entity = entity_fields[0] if entity_fields else None
    sampled_entity_count = (
        len(
            {
                str(row[primary_entity])
                for row in sample
                if row.get(primary_entity) not in (None, "")
            }
        )
        if primary_entity
        else 0
    )

    return ObservationModel(
        shape=shape,
        confidence=confidence,
        entity_fields=entity_fields,
        timestamp_fields=timestamps,
        metric_fields=wide_metrics,
        metric_dimension_fields=metric_dimensions,
        value_fields=values,
        observation_dimension_fields=observation_dimensions,
        unit_fields=units,
        sample_row_count=len(sample),
        sampled_entity_count=sampled_entity_count,
        statistics=stats,
    )
