"""Select the best observable field for entity state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .observable_inference import ObservableInference


@dataclass(frozen=True, slots=True)
class StateSelection:
    field: str
    confidence: int
    reasons: tuple[str, ...]


def select_state_field(observables: Iterable[ObservableInference]) -> StateSelection | None:
    """Select the strongest observable deterministically."""
    candidates = tuple(observables)
    if not candidates:
        return None
    best = min(candidates, key=lambda item: (-item.confidence, item.kind, item.field.casefold()))
    return StateSelection(best.field, best.confidence, best.reasons + ("highest-confidence observable",))
