"""Structured explainability records for inference pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ExplanationNode:
    subject: str
    conclusion: str
    confidence: int
    reasons: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExplanationGraph:
    nodes: tuple[ExplanationNode, ...]

    def for_subject(self, subject: str) -> tuple[ExplanationNode, ...]:
        """Return all explanations for one subject."""
        return tuple(node for node in self.nodes if node.subject == subject)


def build_explanation_graph(nodes: Iterable[ExplanationNode]) -> ExplanationGraph:
    """Build a deterministic graph ordered by subject and confidence."""
    return ExplanationGraph(
        tuple(sorted(nodes, key=lambda item: (item.subject.casefold(), -item.confidence, item.conclusion)))
    )
