"""Plan entities from inferred observables without Home Assistant imports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .observable_inference import ObservableInference


@dataclass(frozen=True, slots=True)
class EntityPlan:
    """One planned entity."""

    source_id: str
    unique_key: str
    state_field: str
    observable_kind: str
    unit: str | None = None
    attributes: tuple[str, ...] = ()


def plan_entities(
    source_id: str,
    observables: Iterable[ObservableInference],
) -> tuple[EntityPlan, ...]:
    """Create one deterministic entity plan per observable."""
    plans = (
        EntityPlan(
            source_id=source_id,
            unique_key=f"{source_id}:{item.kind}:{item.field}",
            state_field=item.field,
            observable_kind=item.kind,
            unit=item.unit,
        )
        for item in observables
    )
    return tuple(sorted(plans, key=lambda item: (item.observable_kind, item.state_field.casefold())))
