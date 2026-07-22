"""Translate user-classified rows into stable Home Assistant observations."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha1
import math
import re
from typing import Any, Iterable, Mapping

from .field_roles import (
    FIELD_ROLE_DATA,
    FIELD_ROLE_MEASUREMENT_NAME,
    FIELD_ROLE_TIME,
)
from .models import SemanticObservation
from .record_structure import RecordStructure, encode_unit_key


def _time_key(value: object, index: int) -> tuple[int, object, int]:
    if isinstance(value, datetime):
        return (2, value.timestamp(), index)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return (1, value, index)
        return (2, parsed.timestamp(), index)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (2, float(value), index)
    return (0, "", index)


def _joined(row: Mapping[str, Any], fields: Iterable[str]) -> str | None:
    values = [str(row[field]) for field in fields if row.get(field) not in (None, "")]
    return " / ".join(values) if values else None


def _stream_id(unit_id: str | None, metric: str) -> str:
    raw = f"{unit_id or 'dataset'}\0{metric}".encode()
    return sha1(raw, usedforsecurity=False).hexdigest()[:20]


def _measurement_value(value: Any) -> Any:
    """Preserve text while turning CSV numeric measurements into HA numbers."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    try:
        if re.fullmatch(r"[+-]?\d+", stripped):
            return int(stripped)
        number = float(stripped)
    except ValueError:
        return value
    return number if math.isfinite(number) else value


def normalize_observations(
    rows: Iterable[Mapping[str, Any]],
    *,
    field_roles: Mapping[str, str],
    structure: RecordStructure,
    selected_fields: Iterable[str] | None = None,
    unit_id: str | None = None,
) -> dict[str, SemanticObservation]:
    """Return the latest logical stream values from wide or long physical rows."""
    data_fields = tuple(
        field for field, role in field_roles.items() if role == FIELD_ROLE_DATA
    )
    selected = set(selected_fields) if selected_fields is not None else None
    if selected is not None:
        data_fields = tuple(field for field in data_fields if field in selected)
    metric_name_fields = tuple(
        field
        for field, role in field_roles.items()
        if role == FIELD_ROLE_MEASUREMENT_NAME
    )
    time_fields = tuple(
        field for field, role in field_roles.items() if role == FIELD_ROLE_TIME
    )
    latest: dict[str, tuple[tuple[int, object, int], SemanticObservation]] = {}

    for index, raw_row in enumerate(rows):
        row = dict(raw_row)
        resolved_unit = unit_id
        if resolved_unit is None and structure.unit_key_fields:
            values = tuple(row.get(field) for field in structure.unit_key_fields)
            if all(value not in (None, "") for value in values):
                resolved_unit = encode_unit_key(values)
        timestamp = _joined(row, time_fields)
        record_values = tuple(row.get(field) for field in structure.record_key_fields)
        record_id = (
            encode_unit_key(record_values)
            if record_values and all(value not in (None, "") for value in record_values)
            else None
        )
        record_label = _joined(row, structure.record_label_fields)
        metric_name = _joined(row, metric_name_fields)

        for field in data_fields:
            value = row.get(field)
            if value is None:
                continue
            metric = metric_name or field
            if metric_name and len(data_fields) > 1:
                metric = f"{metric_name} / {field}"
            stream_id = _stream_id(resolved_unit, metric)
            observation = SemanticObservation(
                stream_id=stream_id,
                unit_id=resolved_unit,
                metric=metric,
                source_field=field,
                value=_measurement_value(value),
                timestamp=timestamp,
                record_id=record_id,
                record_label=record_label,
                source_row=row,
            )
            key = _time_key(timestamp, index)
            previous = latest.get(stream_id)
            if previous is None or key >= previous[0]:
                latest[stream_id] = (key, observation)

    return {stream_id: value[1] for stream_id, value in latest.items()}
