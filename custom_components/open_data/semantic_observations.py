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
from .models import ObservationPoint, SemanticObservation
from .record_structure import RecordStructure, encode_unit_key

_UNIT_FIELD_NAMES = {
    "unit",
    "units",
    "uom",
    "unit_of_measurement",
    "measurement_unit",
}


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
    values = [
        _display_text(row[field])
        for field in fields
        if row.get(field) not in (None, "")
    ]
    return " / ".join(values) if values else None


def _display_text(value: object) -> str:
    return " ".join(str(value).strip().split())


def _canonical_text(value: object) -> str:
    """Normalize equivalent categorical representations for stream identity."""
    text = _display_text(value)
    try:
        number = float(text)
    except ValueError:
        return text.casefold()
    if not math.isfinite(number):
        return text.casefold()
    return format(number, ".15g")


def _stream_id(
    unit_id: str | None,
    metric: str,
    dimensions: tuple[tuple[str, str], ...],
) -> str:
    canonical_dimensions = tuple(
        (field.casefold(), _canonical_text(value)) for field, value in dimensions
    )
    raw = repr(
        (
            _canonical_text(unit_id or "dataset"),
            _canonical_text(metric),
            canonical_dimensions,
        )
    ).encode()
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


def _unit_field(rows: Iterable[Mapping[str, Any]]) -> str | None:
    names = {
        str(field).strip().casefold(): str(field)
        for row in rows
        for field in row
    }
    return next((names[name] for name in _UNIT_FIELD_NAMES if name in names), None)


def normalize_observations(
    rows: Iterable[Mapping[str, Any]],
    *,
    field_roles: Mapping[str, str],
    structure: RecordStructure,
    selected_fields: Iterable[str] | None = None,
    unit_id: str | None = None,
) -> dict[str, SemanticObservation]:
    """Return the latest logical stream values from wide or long physical rows."""
    materialized = tuple(rows)
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
    unit_field = _unit_field(materialized)
    latest: dict[str, tuple[tuple[int, object, int], SemanticObservation]] = {}
    history: dict[str, dict[str, ObservationPoint]] = {}

    for index, raw_row in enumerate(materialized):
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
        dimensions = tuple(
            (field, _display_text(row[field]))
            for field in metric_name_fields
            if row.get(field) not in (None, "")
        )
        source_unit = (
            _display_text(row[unit_field])
            if unit_field and row.get(unit_field) not in (None, "")
            else None
        )
        identity_dimensions = dimensions
        if source_unit is not None:
            identity_dimensions = (*dimensions, ("unit", source_unit))

        for field in data_fields:
            value = row.get(field)
            if value is None:
                continue
            metric = metric_name or field
            if metric_name and len(data_fields) > 1:
                metric = f"{metric_name} / {field}"
            stream_id = _stream_id(resolved_unit, metric, identity_dimensions)
            observation = SemanticObservation(
                stream_id=stream_id,
                unit_id=resolved_unit,
                metric=metric,
                source_field=field,
                value=_measurement_value(value),
                timestamp=timestamp,
                unit=source_unit,
                dimensions=dimensions,
                record_id=record_id,
                record_label=record_label,
                source_row=row,
            )
            numeric_value = observation.value
            if (
                timestamp is not None
                and isinstance(numeric_value, (int, float))
                and not isinstance(numeric_value, bool)
            ):
                history.setdefault(stream_id, {})[timestamp] = ObservationPoint(
                    timestamp, numeric_value
                )
            key = _time_key(timestamp, index)
            previous = latest.get(stream_id)
            if previous is None or key >= previous[0]:
                latest[stream_id] = (key, observation)

    normalized: dict[str, SemanticObservation] = {}
    for stream_id, (_, observation) in latest.items():
        points = tuple(
            sorted(
                history.get(stream_id, {}).values(),
                key=lambda point: _time_key(point.timestamp, 0),
            )
        )
        normalized[stream_id] = SemanticObservation(
            stream_id=observation.stream_id,
            unit_id=observation.unit_id,
            metric=observation.metric,
            source_field=observation.source_field,
            value=observation.value,
            timestamp=observation.timestamp,
            unit=observation.unit,
            dimensions=observation.dimensions,
            record_id=observation.record_id,
            record_label=observation.record_label,
            history=points,
            source_row=observation.source_row,
        )
    return normalized
