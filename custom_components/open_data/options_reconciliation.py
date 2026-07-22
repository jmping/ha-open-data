"""Reconcile persisted options with a newly reviewed dataset structure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .record_structure import RecordSelection, decode_unit_key


@dataclass(frozen=True, slots=True)
class ReconciledOptions:
    """Selections that remain valid after an options or schema change."""

    selected_records: tuple[str, ...]
    selected_fields: tuple[str, ...]


def _values(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if not isinstance(raw, Sequence):
        return ()
    return tuple(dict.fromkeys(str(value) for value in raw if value not in (None, "")))


def reconcile_options(
    *,
    raw_records: object,
    records_were_configured: bool,
    available_records: Iterable[RecordSelection],
    unit_key_fields: Sequence[str],
    raw_fields: object,
    fields_were_configured: bool,
    available_fields: Iterable[str],
) -> ReconciledOptions:
    """Preserve explicit empties and migrate valid legacy single-key selections."""
    available = tuple(available_records)
    by_value = {record.value: record for record in available}
    by_filters = {
        record.filters: record.value
        for record in available
        if getattr(record, "filters", ())
    }
    selected_records: list[str] = []
    if records_were_configured:
        for value in _values(raw_records):
            resolved = value if value in by_value else None
            if resolved is None:
                filters = tuple(decode_unit_key(value, unit_key_fields).items())
                resolved = by_filters.get(filters)
            if resolved and resolved not in selected_records:
                selected_records.append(resolved)
    else:
        selected_records = list(by_value)

    valid_fields = set(available_fields)
    selected_fields = (
        tuple(field for field in _values(raw_fields) if field in valid_fields)
        if fields_were_configured
        else tuple(valid_fields)
    )
    return ReconciledOptions(tuple(selected_records), selected_fields)
