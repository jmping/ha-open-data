"""Optional authoritative geographic reference hints.

Reference knowledge supplements, but never replaces, generic relationship
inference. This module intentionally has no network dependency at runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Mapping, Sequence

from .hierarchy_relationships import (
    RELATION_PERFECT,
    HierarchyRelationship,
    analyze_relationship,
)


@lru_cache(maxsize=1)
def load_us_fips_reference() -> dict[str, object]:
    """Load the bundled Census/ANSI reference data."""
    path = files("custom_components.open_data").joinpath("data/us_fips_reference.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def fips_field_kinds(fields: Sequence[str]) -> dict[str, str]:
    """Return recognized FIPS geography kinds keyed by actual dataset field."""
    reference = load_us_fips_reference()
    aliases = reference.get("field_aliases")
    if not isinstance(aliases, Mapping):
        return {}
    normalized_aliases: dict[str, str] = {}
    for kind, raw_values in aliases.items():
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
            continue
        for raw in raw_values:
            normalized_aliases[_normalized(str(raw))] = str(kind)
    recognized: dict[str, str] = {}
    for field in fields:
        kind = normalized_aliases.get(_normalized(field))
        if kind:
            recognized[field] = kind
    return recognized


def fips_relationship_hints(
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> tuple[HierarchyRelationship, ...]:
    """Return parent-scoped identity hints for recognized FIPS code columns."""
    kinds = fips_field_kinds(fields)
    by_kind: dict[str, str] = {}
    for field, kind in kinds.items():
        by_kind.setdefault(kind, field)

    reference = load_us_fips_reference()
    raw_rules = reference.get("composite_identities")
    if not isinstance(raw_rules, Sequence):
        return ()

    hints: list[HierarchyRelationship] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, Mapping):
            continue
        child_kind = str(raw_rule.get("child_kind") or "")
        parent_kind = str(raw_rule.get("parent_kind") or "")
        child = by_kind.get(child_kind)
        parent = by_kind.get(parent_kind)
        if not child or not parent or child == parent:
            continue
        inferred = analyze_relationship(rows, child, parent)
        identity_fields = (parent, child)
        warning = inferred.warning
        if inferred.evidence.multi_parent_children:
            warning = (
                f"{child} is a parent-scoped FIPS/ANSI code; repeated values under "
                f"different {parent} values are expected. Identity is qualified as "
                f"({parent}, {child})."
            )
        hints.append(
            HierarchyRelationship(
                child_field=child,
                parent_field=parent,
                relation=RELATION_PERFECT,
                confidence=0.99,
                evidence=inferred.evidence,
                source="fips_reference",
                identity_fields=identity_fields,
                warning=warning,
            )
        )
    return tuple(hints)
