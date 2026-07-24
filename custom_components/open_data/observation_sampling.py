"""Provider-independent bounded historical observation sampling helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


def _parse_timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _entity_value(row: Mapping[str, Any], identity_fields: Sequence[str]) -> str | None:
    values = [
        str(row[field]).strip()
        for field in identity_fields
        if row.get(field) not in (None, "")
    ]
    return "|".join(values) if values else None


@dataclass(frozen=True, slots=True)
class ObservationSamplingEvidence:
    """Diagnostics describing one bounded historical sample."""

    requested_limit: int
    source_row_count: int
    sampled_row_count: int
    entity_count: int
    timestamp_count: int
    time_start: str | None
    time_end: str | None
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        """Return stable diagnostics for services and persisted analysis."""
        return {
            "requested_limit": self.requested_limit,
            "source_row_count": self.source_row_count,
            "sampled_row_count": self.sampled_row_count,
            "entity_count": self.entity_count,
            "timestamp_count": self.timestamp_count,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class ObservationSample:
    """A bounded, time- and entity-spread observation sample."""

    rows: tuple[Mapping[str, Any], ...]
    evidence: ObservationSamplingEvidence


@dataclass(frozen=True, slots=True)
class FunctionalDependency:
    """Observed parent-to-child relationship in a bounded sample."""

    parent_field: str
    child_field: str
    parent_count: int
    child_count: int
    confidence: float

    def as_dict(self) -> dict[str, Any]:
        """Return stable diagnostics for explorer and review flows."""
        return {
            "parent_field": self.parent_field,
            "child_field": self.child_field,
            "parent_count": self.parent_count,
            "child_count": self.child_count,
            "confidence": round(self.confidence, 4),
        }


def stratify_observation_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    timestamp_field: str | None,
    identity_fields: Sequence[str] = (),
    limit: int = 200,
) -> ObservationSample:
    """Select a deterministic bounded sample spread across time and entities.

    Providers may return a capped candidate window in any physical order. This
    helper normalizes that window and chooses rows in round-robin entity order,
    alternating newest and oldest remaining observations for each entity. The
    result therefore avoids the common first-N bias while remaining bounded.
    """
    cap = max(1, int(limit))
    materialized = list(rows)
    indexed: list[tuple[datetime | None, str, int, Mapping[str, Any]]] = []
    for index, row in enumerate(materialized):
        timestamp = (
            _parse_timestamp(row.get(timestamp_field)) if timestamp_field else None
        )
        entity = _entity_value(row, identity_fields) or ""
        indexed.append((timestamp, entity, index, row))

    indexed.sort(
        key=lambda item: (
            item[1],
            item[0] is None,
            item[0] or datetime.min.replace(tzinfo=timezone.utc),
            item[2],
        )
    )
    groups: dict[str, list[tuple[datetime | None, str, int, Mapping[str, Any]]]] = {}
    for item in indexed:
        groups.setdefault(item[1], []).append(item)

    ordered_entities = sorted(groups)
    selected: list[tuple[datetime | None, str, int, Mapping[str, Any]]] = []
    depth = 0
    while len(selected) < cap:
        added = False
        for entity in ordered_entities:
            group = groups[entity]
            offsets = (-(depth + 1), depth)
            for offset in offsets:
                try:
                    item = group[offset]
                except IndexError:
                    continue
                if item in selected:
                    continue
                selected.append(item)
                added = True
                if len(selected) >= cap:
                    break
            if len(selected) >= cap:
                break
        if not added:
            break
        depth += 1

    selected.sort(
        key=lambda item: (
            item[0] is None,
            item[0] or datetime.max.replace(tzinfo=timezone.utc),
            item[1],
            item[2],
        )
    )
    timestamps = [item[0] for item in selected if item[0] is not None]
    entities = {item[1] for item in selected if item[1]}
    evidence = ObservationSamplingEvidence(
        requested_limit=cap,
        source_row_count=len(materialized),
        sampled_row_count=len(selected),
        entity_count=len(entities),
        timestamp_count=len(timestamps),
        time_start=min(timestamps).isoformat() if timestamps else None,
        time_end=max(timestamps).isoformat() if timestamps else None,
        truncated=len(materialized) > len(selected),
    )
    return ObservationSample(tuple(item[3] for item in selected), evidence)


def infer_functional_dependencies(
    rows: Iterable[Mapping[str, Any]],
    *,
    fields: Sequence[str],
    minimum_parent_values: int = 2,
    minimum_confidence: float = 0.95,
) -> tuple[FunctionalDependency, ...]:
    """Infer conservative parent/child relationships from bounded observations.

    A parent field functionally determines a child field when each observed
    parent value maps to one child value. Confidence is the fraction of parent
    groups that satisfy that rule, allowing a small amount of dirty source data
    without manufacturing a hierarchy from weak evidence.
    """
    materialized = tuple(rows)
    dependencies: list[FunctionalDependency] = []
    for parent in fields:
        for child in fields:
            if parent == child:
                continue
            groups: dict[str, set[str]] = {}
            for row in materialized:
                parent_value = row.get(parent)
                child_value = row.get(child)
                if parent_value in (None, "") or child_value in (None, ""):
                    continue
                groups.setdefault(str(parent_value), set()).add(str(child_value))
            if len(groups) < max(2, minimum_parent_values):
                continue
            stable = sum(len(values) == 1 for values in groups.values())
            confidence = stable / len(groups)
            child_values = {value for values in groups.values() for value in values}
            if confidence < minimum_confidence or len(child_values) <= 1:
                continue
            dependencies.append(
                FunctionalDependency(
                    parent_field=parent,
                    child_field=child,
                    parent_count=len(groups),
                    child_count=len(child_values),
                    confidence=confidence,
                )
            )
    dependencies.sort(
        key=lambda item: (
            -item.confidence,
            item.parent_count,
            item.child_count,
            item.parent_field,
            item.child_field,
        )
    )
    return tuple(dependencies)
