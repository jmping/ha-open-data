"""Infer and persist pairwise structural relationships between dataset fields.

A hierarchy is not assumed to be one linear path.  The canonical model is a set
of directed child -> parent dyads.  A field may therefore have multiple parents
(e.g. precinct -> city and precinct -> county) while sibling fields remain
unrelated (e.g. city and ZIP can both nest under state).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

RELATION_PERFECT = "perfect"
RELATION_IMPERFECT = "imperfect"
RELATION_NONE = "none"
RELATION_UNKNOWN = "unknown"
RELATION_KINDS = (
    RELATION_PERFECT,
    RELATION_IMPERFECT,
    RELATION_NONE,
    RELATION_UNKNOWN,
)


@dataclass(frozen=True, slots=True)
class RelationshipEvidence:
    """Observed support for one child -> parent relationship."""

    observed_children: int = 0
    observed_pairs: int = 0
    multi_parent_children: int = 0
    missing_child_rows: int = 0
    missing_parent_rows: int = 0

    @property
    def violation_rate(self) -> float | None:
        """Return the share of observed child labels associated with >1 parent."""
        if not self.observed_children:
            return None
        return self.multi_parent_children / self.observed_children


@dataclass(frozen=True, slots=True)
class HierarchyRelationship:
    """One editable child -> parent dyad."""

    child_field: str
    parent_field: str
    relation: str
    confidence: float
    evidence: RelationshipEvidence
    source: str = "inferred"
    identity_fields: tuple[str, ...] = ()
    warning: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a config-entry-safe representation."""
        return {
            "child_field": self.child_field,
            "parent_field": self.parent_field,
            "relation": self.relation,
            "confidence": self.confidence,
            "evidence": asdict(self.evidence),
            "source": self.source,
            "identity_fields": list(self.identity_fields),
            "warning": self.warning,
        }


def _present(value: object) -> bool:
    return value not in (None, "")


def analyze_relationship(
    rows: Iterable[Mapping[str, object]],
    child_field: str,
    parent_field: str,
) -> HierarchyRelationship:
    """Infer one directed functional relationship from a bounded row sample.

    "Perfect" means every observed child label maps to one parent label in the
    sample.  A repeated child label under multiple parents is *not* treated as
    corrupt data: it is inferred as imperfect and can later be explicitly
    promoted by the user, which qualifies the child identity by its parent.
    """
    if child_field == parent_field:
        raise ValueError("A hierarchy relationship needs two different fields")

    parents_by_child: dict[str, set[str]] = {}
    pairs: set[tuple[str, str]] = set()
    missing_child = 0
    missing_parent = 0
    for row in rows:
        child = row.get(child_field)
        parent = row.get(parent_field)
        if not _present(child):
            missing_child += 1
            continue
        if not _present(parent):
            missing_parent += 1
            continue
        child_key = str(child)
        parent_key = str(parent)
        parents_by_child.setdefault(child_key, set()).add(parent_key)
        pairs.add((child_key, parent_key))

    observed = len(parents_by_child)
    conflicts = sum(1 for values in parents_by_child.values() if len(values) > 1)
    evidence = RelationshipEvidence(
        observed_children=observed,
        observed_pairs=len(pairs),
        multi_parent_children=conflicts,
        missing_child_rows=missing_child,
        missing_parent_rows=missing_parent,
    )
    if not observed:
        return HierarchyRelationship(
            child_field,
            parent_field,
            RELATION_UNKNOWN,
            0.0,
            evidence,
        )
    if conflicts == 0:
        # This is evidence from a bounded sample, not a schema guarantee.
        confidence = min(0.99, 0.55 + min(observed, 100) / 250)
        return HierarchyRelationship(
            child_field,
            parent_field,
            RELATION_PERFECT,
            confidence,
            evidence,
        )
    confidence = min(0.99, 0.6 + conflicts / max(observed, 1) * 0.39)
    return HierarchyRelationship(
        child_field,
        parent_field,
        RELATION_IMPERFECT,
        confidence,
        evidence,
        warning=(
            f"{conflicts} observed {child_field!r} values map to multiple "
            f"{parent_field!r} values"
        ),
    )


def infer_relationships(
    rows: Sequence[Mapping[str, object]],
    fields: Iterable[str],
) -> tuple[HierarchyRelationship, ...]:
    """Infer all directed dyads worth presenting for review.

    Perfect and imperfect dependencies are retained. Unknown dyads are omitted
    from the default UI to avoid producing O(n^2) noise; users may still add a
    relationship manually.
    """
    field_names = tuple(dict.fromkeys(field for field in fields if field))
    relationships: list[HierarchyRelationship] = []
    for child in field_names:
        for parent in field_names:
            if child == parent:
                continue
            relation = analyze_relationship(rows, child, parent)
            if relation.relation != RELATION_UNKNOWN:
                relationships.append(relation)
    return tuple(relationships)


def apply_user_relationship(
    inferred: HierarchyRelationship,
    relation: str,
) -> HierarchyRelationship:
    """Apply a user edit while preserving evidence and collision warnings.

    If a user declares a relationship perfect despite repeated child labels
    appearing under multiple parents, interpret that as an identity hint rather
    than silently rejecting it.  The canonical child identity is qualified by
    the parent (e.g. ``Washington County`` + ``Oregon``), and the apparent
    contradiction remains visible as a warning.
    """
    if relation not in RELATION_KINDS:
        raise ValueError(f"Unknown hierarchy relationship: {relation}")

    identity_fields: tuple[str, ...] = ()
    warning: str | None = None
    if relation == RELATION_PERFECT and inferred.evidence.multi_parent_children:
        identity_fields = (inferred.child_field, inferred.parent_field)
        warning = (
            "Observed child labels occur under multiple parents. Treating the "
            "user-selected perfect relationship as a parent-qualified identity; "
            "review if the child field is itself a stable global identifier."
        )
    return HierarchyRelationship(
        child_field=inferred.child_field,
        parent_field=inferred.parent_field,
        relation=relation,
        confidence=1.0,
        evidence=inferred.evidence,
        source="user",
        identity_fields=identity_fields,
        warning=warning,
    )


def load_relationships(raw: object) -> tuple[HierarchyRelationship, ...]:
    """Load persisted dyads defensively."""
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return ()
    loaded: list[HierarchyRelationship] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        child = str(item.get("child_field") or "")
        parent = str(item.get("parent_field") or "")
        relation = str(item.get("relation") or RELATION_UNKNOWN)
        if not child or not parent or child == parent or relation not in RELATION_KINDS:
            continue
        evidence_raw = item.get("evidence")
        evidence_map = evidence_raw if isinstance(evidence_raw, Mapping) else {}
        evidence = RelationshipEvidence(
            observed_children=int(evidence_map.get("observed_children") or 0),
            observed_pairs=int(evidence_map.get("observed_pairs") or 0),
            multi_parent_children=int(evidence_map.get("multi_parent_children") or 0),
            missing_child_rows=int(evidence_map.get("missing_child_rows") or 0),
            missing_parent_rows=int(evidence_map.get("missing_parent_rows") or 0),
        )
        identity_raw = item.get("identity_fields")
        identity = (
            tuple(str(value) for value in identity_raw if value)
            if isinstance(identity_raw, Sequence) and not isinstance(identity_raw, (str, bytes))
            else ()
        )
        loaded.append(
            HierarchyRelationship(
                child_field=child,
                parent_field=parent,
                relation=relation,
                confidence=float(item.get("confidence") or 0.0),
                evidence=evidence,
                source=str(item.get("source") or "inferred"),
                identity_fields=identity,
                warning=str(item["warning"]) if item.get("warning") else None,
            )
        )
    return tuple(loaded)


def relationships_from_paths(
    paths: Iterable[Iterable[str]],
) -> tuple[HierarchyRelationship, ...]:
    """Translate legacy broad -> narrow hierarchy paths into perfect dyads."""
    relationships: dict[tuple[str, str], HierarchyRelationship] = {}
    for raw_path in paths:
        path = tuple(dict.fromkeys(field for field in raw_path if field))
        for parent, child in zip(path, path[1:]):
            key = (child, parent)
            relationships[key] = HierarchyRelationship(
                child_field=child,
                parent_field=parent,
                relation=RELATION_PERFECT,
                confidence=1.0,
                evidence=RelationshipEvidence(),
                source="legacy_path",
            )
    return tuple(relationships.values())
