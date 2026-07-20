"""Build structured diagnostics for provider-neutral planning decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PlanningDecision:
    subject: str
    selected: str | None
    reasons: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanningDiagnostics:
    decisions: tuple[PlanningDecision, ...]

    def for_subject(self, subject: str) -> PlanningDecision | None:
        return next((item for item in self.decisions if item.subject == subject), None)


def build_planning_diagnostics(decisions: Iterable[PlanningDecision]) -> PlanningDiagnostics:
    """Return stable diagnostics sorted by subject."""
    return PlanningDiagnostics(tuple(sorted(decisions, key=lambda item: item.subject.casefold())))
