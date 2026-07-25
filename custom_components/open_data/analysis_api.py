"""Stable analysis boundary for config flow and options flow callers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, overload

from .analyzer import (
    DatasetStructure,
    SelectableRecord,
    build_selectable_records as _build_selectable_records,
)
from .models import OpenDataDataset


@overload
def build_selectable_records(
    rows: list[dict[str, Any]],
    structure: DatasetStructure,
    *,
    limit: int | None = None,
) -> list[SelectableRecord]: ...


@overload
def build_selectable_records(
    dataset: OpenDataDataset,
    rows: list[dict[str, Any]],
    identity_fields: Sequence[str],
    display_fields: Sequence[str],
    *,
    limit: int | None = None,
) -> list[str]: ...


def build_selectable_records(
    first: OpenDataDataset | list[dict[str, Any]],
    second: DatasetStructure | list[dict[str, Any]],
    identity_fields: Sequence[str] = (),
    display_fields: Sequence[str] = (),
    *,
    limit: int | None = None,
) -> list[SelectableRecord] | list[str]:
    """Build records through one validated, bounded API.

    Runtime/options callers pass sampled rows plus a ``DatasetStructure`` and
    receive rich ``SelectableRecord`` objects. Config-entry preparation passes
    an ``OpenDataDataset`` plus sampled rows and receives only stable string
    identifiers, which are safe to persist in Home Assistant storage.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")

    if isinstance(first, OpenDataDataset):
        if not isinstance(second, list) or not all(
            isinstance(row, Mapping) for row in second
        ):
            raise TypeError("dataset record selection requires a list of row mappings")
        identity = next((field for field in identity_fields if field), None)
        display = next((field for field in display_fields if field), None)
        structure = DatasetStructure(
            kind="records",
            profile_id=None,
            confidence=1.0,
            identity_field=identity,
            display_field=display,
            timestamp_field=None,
            geometry_field=None,
            geometry_type=None,
            hierarchy_fields=(),
            metric_fields=(),
            ignored_fields=(),
            identity_fields=tuple(identity_fields),
            display_fields=tuple(display_fields),
        )
        records = _bounded(_build_selectable_records(second, structure), limit)
        return [record.value for record in records]

    if not isinstance(second, DatasetStructure):
        raise TypeError("row record selection requires a DatasetStructure")
    if not isinstance(first, list) or not all(isinstance(row, Mapping) for row in first):
        raise TypeError("row record selection requires a list of row mappings")
    return _bounded(_build_selectable_records(first, second), limit)


def _bounded(records: Iterable[SelectableRecord], limit: int | None) -> list[SelectableRecord]:
    """Return a deterministic bounded list without changing record semantics."""
    result = list(records)
    return result if limit is None else result[:limit]
