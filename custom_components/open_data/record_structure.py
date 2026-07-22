"""User-reviewed unit and record identity for tabular open data."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import json
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

    @property
    def unit_label_fields(self) -> tuple[str, ...]:
        """Return all configured parent-to-child label fields."""
        return tuple(field for level in self.levels for field in level.label_fields)


@dataclass(slots=True, frozen=True)
class RecordSelection:
    """One user-selectable stable unit."""

    value: str
    label: str
    filters: tuple[tuple[str, str], ...]


_SELECTION_PREFIX = "v1:"


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


def load_record_structure(raw: Mapping[str, object] | None) -> RecordStructure:
    """Load a persisted structure while tolerating missing optional values."""
    if not raw:
        return RecordStructure(())
    levels = raw.get("levels", ())
    if not isinstance(levels, Sequence) or isinstance(levels, (str, bytes)):
        levels = ()
    return build_record_structure(
        parent_levels=tuple(level for level in levels if isinstance(level, Mapping)),
        record_key_fields=_sequence(raw.get("record_key_fields")),
        record_label_fields=_sequence(raw.get("record_label_fields")),
    )


def legacy_record_structure(
    identity_field: str | None,
    display_field: str | None,
    timestamp_field: str | None,
) -> RecordStructure:
    """Represent a version-one single-field configuration in the new model."""
    return build_record_structure(
        unit_key_fields=(identity_field,) if identity_field else (),
        unit_label_fields=(display_field,) if identity_field and display_field else (),
        record_key_fields=tuple(
            field for field in (identity_field, timestamp_field) if field
        ),
        record_label_fields=tuple(
            field for field in (display_field, timestamp_field) if field
        ),
    )


def _sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if item not in (None, ""))


def encode_unit_key(values: Sequence[object]) -> str:
    """Encode a composite key into a reversible config-entry value."""
    payload = json.dumps(
        ["" if value is None else str(value) for value in values],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{_SELECTION_PREFIX}{token}"


def decode_unit_key(value: str, fields: Sequence[str]) -> dict[str, str]:
    """Decode a selection, accepting legacy single-field config values."""
    if not value.startswith(_SELECTION_PREFIX):
        return {fields[0]: value} if len(fields) == 1 else {}
    token = value.removeprefix(_SELECTION_PREFIX)
    try:
        padding = "=" * (-len(token) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(token + padding))
    except (ValueError, TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(decoded, list) or len(decoded) != len(fields):
        return {}
    return {field: str(item) for field, item in zip(fields, decoded, strict=True)}


def build_record_selections(
    rows: Iterable[Mapping[str, object]],
    structure: RecordStructure,
) -> tuple[RecordSelection, ...]:
    """Build deduplicated choices from composite unit keys and labels."""
    key_fields = structure.unit_key_fields
    if not key_fields:
        return ()
    label_fields = structure.unit_label_fields
    selections: dict[str, RecordSelection] = {}
    for row in rows:
        values = tuple(row.get(field) for field in key_fields)
        if any(value in (None, "") for value in values):
            continue
        token = encode_unit_key(values)
        label_parts = [
            str(row[field])
            for field in label_fields
            if row.get(field) not in (None, "")
        ]
        label = " / ".join(dict.fromkeys(label_parts)) or " / ".join(
            str(value) for value in values
        )
        selections.setdefault(
            token,
            RecordSelection(
                value=token,
                label=label,
                filters=tuple(
                    (field, str(value))
                    for field, value in zip(key_fields, values, strict=True)
                ),
            ),
        )
    return tuple(sorted(selections.values(), key=lambda item: item.label.casefold()))
