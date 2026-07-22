"""User-reviewed unit and record identity for tabular open data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(slots=True, frozen=True)
class RecordLevel:
    """One stable unit in an outer-to-inner hierarchy."""

    name: str
    key_fields: tuple[str, ...]
    label_fields: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class RecordStructure:
    """Describe nested units and the observations belonging to them."""

    levels: tuple[RecordLevel, ...]
    record_key_fields: tuple[str, ...] = ()
    record_label_fields: tuple[str, ...] = ()

    @property
    def unit_key_fields(self) -> tuple[str, ...]:
        """Return the composite key of the innermost unit."""
        return tuple(field for level in self.levels for field in level.key_fields)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable persisted representation."""
        return {
            "levels": [
                {
                    "name": level.name,
                    "key_fields": list(level.key_fields),
                    "label_fields": list(level.label_fields),
                }
                for level in self.levels
            ],
            "record_key_fields": list(self.record_key_fields),
            "record_label_fields": list(self.record_label_fields),
        }


def _fields(values: Iterable[str]) -> tuple[str, ...]:
    """Keep field order while removing blanks and duplicates."""
    return tuple(dict.fromkeys(value for value in values if value))


def build_record_structure(
    *,
    unit_key_fields: Iterable[str] = (),
    unit_label_fields: Iterable[str] = (),
    record_key_fields: Iterable[str] = (),
    record_label_fields: Iterable[str] = (),
    parent_levels: Sequence[Mapping[str, object]] = (),
    allowed_fields: Iterable[str] | None = None,
) -> RecordStructure:
    """Build and validate a composite, potentially nested record structure.

    Parent levels are ordered from broadest to narrowest. A level may combine
    any number of fields into its key or readable label. Fields do not have to
    participate in either identity, which deliberately permits constant and
    unassigned columns to remain outside the structure.
    """
    allowed = set(allowed_fields) if allowed_fields is not None else None
    levels: list[RecordLevel] = []
    for index, raw_level in enumerate(parent_levels, start=1):
        name = str(raw_level.get("name") or f"level_{index}")
        keys = _fields(raw_level.get("key_fields", ()))  # type: ignore[arg-type]
        labels = _fields(raw_level.get("label_fields", ()))  # type: ignore[arg-type]
        if not keys:
            raise ValueError(f"Record level {name!r} needs at least one key field")
        levels.append(RecordLevel(name, keys, labels))

    unit_keys = _fields(unit_key_fields)
    unit_labels = _fields(unit_label_fields)
    if unit_keys:
        levels.append(RecordLevel("unit", unit_keys, unit_labels))
    elif unit_labels:
        raise ValueError("A unit label cannot be configured without a unit key")

    record_keys = _fields(record_key_fields)
    record_labels = _fields(record_label_fields)
    used_fields = {
        field
        for level in levels
        for field in (*level.key_fields, *level.label_fields)
    } | set(record_keys) | set(record_labels)
    if allowed is not None and (unknown := used_fields - allowed):
        raise ValueError(f"Unknown or inactive record fields: {sorted(unknown)!r}")

    return RecordStructure(tuple(levels), record_keys, record_labels)
