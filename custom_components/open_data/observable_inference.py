"""Infer canonical observables from normalized field metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .field_aliases import normalize_field_alias
from .unit_detection import detect_unit

_OBSERVABLES = {
    "temperature",
    "relative_humidity",
    "particulate_matter_2_5",
    "particulate_matter_10",
    "precipitation",
    "wind_speed",
    "wind_direction",
    "pressure",
    "water_level",
    "flow_rate",
}


@dataclass(frozen=True, slots=True)
class ObservableInference:
    """One inferred measurable concept."""

    field: str
    kind: str
    confidence: int
    unit: str | None = None
    reasons: tuple[str, ...] = ()


def infer_observable(
    name: str,
    label: str | None = None,
    unit: str | None = None,
) -> ObservableInference | None:
    """Infer an observable from field name, label, and unit metadata."""
    concepts = (normalize_field_alias(name), normalize_field_alias(label or ""))
    kind = next((item for item in concepts if item in _OBSERVABLES), None)
    if kind is None:
        return None
    detected_unit = detect_unit(unit, label=label)
    confidence = 90 if concepts[0] == kind else 75
    reasons = ("canonical field alias",) if concepts[0] == kind else ("canonical label alias",)
    return ObservableInference(
        field=name,
        kind=kind,
        confidence=confidence,
        unit=detected_unit.canonical if detected_unit else None,
        reasons=reasons,
    )


def infer_observables(
    fields: Iterable[tuple[str, str | None, str | None]],
) -> tuple[ObservableInference, ...]:
    """Infer all recognized observables in source order."""
    return tuple(
        inference
        for name, label, unit in fields
        if (inference := infer_observable(name, label, unit)) is not None
    )
