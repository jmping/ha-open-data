"""Build provider-neutral observable relationship graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .observable_inference import ObservableInference


@dataclass(frozen=True, slots=True)
class ObservableNode:
    """One observable attached to a logical source."""

    source_id: str
    observable: ObservableInference


@dataclass(frozen=True, slots=True)
class ObservableGraph:
    """A deterministic grouping of observables by logical source."""

    nodes: tuple[ObservableNode, ...]

    def for_source(self, source_id: str) -> tuple[ObservableInference, ...]:
        return tuple(node.observable for node in self.nodes if node.source_id == source_id)


def build_observable_graph(
    sources: Iterable[tuple[str, Iterable[ObservableInference]]],
) -> ObservableGraph:
    """Build a stable graph preserving source and observable order."""
    return ObservableGraph(
        tuple(
            ObservableNode(source_id, observable)
            for source_id, observables in sources
            for observable in observables
        )
    )
