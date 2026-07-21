"""Translate provider rows into stable semantic observation streams."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha1
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class SemanticObservation:
    """Latest value for one entity, metric, and dimension combination."""

    stream_id: str
    entity_id: str | None
    metric: str
    value: Any
    timestamp: Any = None
    unit: str | None = None
    dimensions: tuple[tuple[str, str], ...] = ()
    source_row: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


def _value(row: dict[str, Any], field_name: str | None) -> Any:
    return row.get(field_name) if field_name else None


def _text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _time_key(value: Any, row_index: int) -> tuple[int, Any, int]:
    """Return a comparable key; later rows win when time is absent or invalid."""
    if isinstance(value, datetime):
        return (2, value.timestamp(), row_index)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return (1, value, row_index)
        return (2, parsed.timestamp(), row_index)
    if isinstance(value, (int, float)):
        return (2, float(value), row_index)
    return (0, 0, row_index)


def stream_identifier(
    entity_id: str | None,
    metric: str,
    dimensions: tuple[tuple[str, str], ...],
) -> str:
    """Build a compact stable identifier independent of row ordering."""
    raw = repr((entity_id or "dataset", metric, dimensions)).encode()
    return sha1(raw, usedforsecurity=False).hexdigest()[:20]


def normalize_observations(
    rows: Iterable[dict[str, Any]],
    *,
    shape: str,
    entity_field: str | None,
    timestamp_field: str | None,
    metric_dimension_fields: tuple[str, ...] = (),
    value_fields: tuple[str, ...] = (),
    observation_dimension_fields: tuple[str, ...] = (),
    unit_fields: tuple[str, ...] = (),
) -> dict[str, SemanticObservation]:
    """Pivot physical rows into latest logical observation streams.

    Long and multi-dimensional data use metric-dimension values as sensor names.
    Wide data emits one stream for each configured value field. Multiple metric
    dimensions are joined so the stream remains stable and human-readable.
    """
    latest: dict[str, tuple[tuple[int, Any, int], SemanticObservation]] = {}
    for index, row in enumerate(rows):
        entity_id = _text(_value(row, entity_field))
        timestamp = _value(row, timestamp_field)
        dimensions = tuple(
            (field_name, str(row[field_name]))
            for field_name in observation_dimension_fields
            if row.get(field_name) not in (None, "")
        )
        unit = next(
            (_text(row.get(field_name)) for field_name in unit_fields if _text(row.get(field_name))),
            None,
        )

        is_long = shape in {"long", "multi_dimensional"} and metric_dimension_fields
        if is_long:
            metric_parts = [
                str(row[field_name])
                for field_name in metric_dimension_fields
                if row.get(field_name) not in (None, "")
            ]
            if not metric_parts:
                continue
            metric = " / ".join(metric_parts)
            fields = value_fields[:1]
        else:
            fields = value_fields

        for value_field in fields:
            value = row.get(value_field)
            if value is None:
                continue
            stream_metric = metric if is_long else value_field
            stream_id = stream_identifier(entity_id, stream_metric, dimensions)
            observation = SemanticObservation(
                stream_id=stream_id,
                entity_id=entity_id,
                metric=stream_metric,
                value=value,
                timestamp=timestamp,
                unit=unit,
                dimensions=dimensions,
                source_row=dict(row),
            )
            key = _time_key(timestamp, index)
            previous = latest.get(stream_id)
            if previous is None or key >= previous[0]:
                latest[stream_id] = (key, observation)

    return {stream_id: item[1] for stream_id, item in latest.items()}
