"""Infer and persist pairwise structural relationships between dataset fields.

A hierarchy is not assumed to be one linear path. The canonical model is a set
of directed child -> parent dyads. A field may therefore have multiple parents
(e.g. precinct -> city and precinct -> county) while sibling fields remain
unrelated (e.g. city and ZIP can both nest under state).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import re
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

_NON_STRUCTURAL_LOCATION_NAMES = {
    "geometry",
    "lat",
    "latitude",
    "lng",
    "lon",
    "long",
    "longitude",
    "shape",
    "the_geom",
    "x_coordinate",
    "y_coordinate",
}


def _normalized_field(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def relationship_candidate_fields(
    rows: Sequence[Mapping[str, object]],
    *,
    identity_fields: Iterable[str] = (),
    location_fields: Iterable[str] = (),
    hierarchy_fields: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return stable categorical fields suitable for automatic dyad inference.

    Coordinate columns are spatial attributes rather than hierarchy levels.
    Row-unique secondary identifiers usually identify observations, not stable
    units, so they are excluded unless their schema also marks them as a
    location or hierarchy field.
    """
    identities = tuple(dict.fromkeys(field for field in identity_fields if field))
    locations = tuple(
        field
        for field in dict.fromkeys(field for field in location_fields if field)
        if _normalized_field(field) not in _NON_STRUCTURAL_LOCATION_NAMES
    )
    hierarchies = tuple(dict.fromkeys(field for field in hierarchy_fields if field))
    stable_context = set((*locations, *hierarchies))
    candidates = list(dict.fromkeys((*hierarchies, *locations)))

    for field in identities:
        if field in candidates:
            continue
        present = [row.get(field) for row in rows if row.get(field) not in (None, "")]
        row_unique = len(present) > 1 and len({str(value) for value in present}) == len(
            present
        )
        if not row_unique or field in stable_context:
            candidates.append(field)
    return tuple(candidates)


@dataclass(frozen=True, slots=True)
class RelationshipEvidence:
    """Observed support for one child -> parent relationship."""

    observed_children: int = 0
    observed_parents: int = 0
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

    @property
    def key(self) -> tuple[str, str]:
        """Return the stable dyad key."""
        return (self.child_field, self.parent_field)

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

    ``perfect`` means every observed child label maps to one parent label in the
    bounded evidence. A repeated child label under multiple parents is not
    treated as corrupt data: it is inferred as imperfect and can later be
    explicitly promoted by the user, which qualifies child identity by parent.
    """
    if child_field == parent_field:
        raise ValueError("A hierarchy relationship needs two different fields")

    parents_by_child: dict[str, set[str]] = {}
    parents: set[str] = set()
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
        parents.add(parent_key)
        pairs.add((child_key, parent_key))

    observed = len(parents_by_child)
    conflicts = sum(1 for values in parents_by_child.values() if len(values) > 1)
    evidence = RelationshipEvidence(
        observed_children=observed,
        observed_parents=len(parents),
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
    """Infer directed dyads worth presenting for review.

    Perfect and imperfect dependencies are retained. Unknown dyads are omitted
    to avoid O(n²) UI noise. Symmetric one-to-one mappings are also omitted when
    neither side is structurally broader: they are aliases/cross-classifiers,
    not evidence of parentage.
    """
    field_names = tuple(dict.fromkeys(field for field in fields if field))
    analyzed: dict[tuple[str, str], HierarchyRelationship] = {}
    for child in field_names:
        for parent in field_names:
            if child == parent:
                continue
            relation = analyze_relationship(rows, child, parent)
            if relation.relation != RELATION_UNKNOWN:
                analyzed[relation.key] = relation

    relationships: list[HierarchyRelationship] = []
    for key, relation in analyzed.items():
        if relation.relation == RELATION_PERFECT:
            reverse = analyzed.get((key[1], key[0]))
            if (
                reverse is not None
                and reverse.relation == RELATION_PERFECT
                and relation.evidence.observed_children
                == relation.evidence.observed_parents
            ):
                # A one-to-one pair does not tell us which field is the parent.
                continue
        relationships.append(relation)
    return tuple(
        sorted(
            relationships,
            key=lambda item: (
                item.parent_field.casefold(),
                item.child_field.casefold(),
            ),
        )
    )


def apply_user_relationship(
    inferred: HierarchyRelationship,
    relation: str,
    *,
    stable_identity_fields: Iterable[str] = (),
) -> HierarchyRelationship:
    """Apply a user edit while preserving evidence and collision warnings.

    If a user declares a relationship perfect despite repeated child labels
    appearing under multiple parents, interpret that as an identity hint rather
    than silently rejecting it. The child identity is parent-qualified (for
    example ``Washington County`` + ``Oregon``). If the child field is already
    declared a stable identity field, retain a stronger contradiction warning;
    the user choice still wins and does not block the import.
    """
    if relation not in RELATION_KINDS:
        raise ValueError(f"Unknown hierarchy relationship: {relation}")

    stable_ids = set(stable_identity_fields)
    identity_fields: tuple[str, ...] = ()
    warning: str | None = None
    if relation == RELATION_PERFECT and inferred.evidence.multi_parent_children:
        identity_fields = (inferred.child_field, inferred.parent_field)
        if inferred.child_field in stable_ids:
            warning = (
                "The configured stable child identifier was observed under multiple "
                "parents. The user-declared perfect relationship is being kept, but "
                "this may indicate a true identifier contradiction rather than only "
                "repeated display labels."
            )
        else:
            warning = (
                "Observed child labels occur under multiple parents. Treating the "
                "user-selected perfect relationship as a parent-qualified identity "
                "rather than assuming the repeated label is corrupt data."
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
            observed_parents=int(evidence_map.get("observed_parents") or 0),
            observed_pairs=int(evidence_map.get("observed_pairs") or 0),
            multi_parent_children=int(evidence_map.get("multi_parent_children") or 0),
            missing_child_rows=int(evidence_map.get("missing_child_rows") or 0),
            missing_parent_rows=int(evidence_map.get("missing_parent_rows") or 0),
        )
        identity_raw = item.get("identity_fields")
        identity = (
            tuple(str(value) for value in identity_raw if value)
            if isinstance(identity_raw, Sequence)
            and not isinstance(identity_raw, (str, bytes))
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


def merge_relationships(
    inferred: Iterable[HierarchyRelationship],
    persisted: Iterable[HierarchyRelationship],
) -> tuple[HierarchyRelationship, ...]:
    """Merge fresh evidence with persisted/user choices.

    User and legacy choices retain their selected relation while new bounded
    evidence refreshes the evidence counts. Inferred relationships not seen in
    the latest bounded sample remain available rather than disappearing.
    """
    fresh = {item.key: item for item in inferred}
    result: dict[tuple[str, str], HierarchyRelationship] = dict(fresh)
    for saved in persisted:
        current = fresh.get(saved.key)
        evidence = current.evidence if current is not None else saved.evidence
        confidence = saved.confidence if saved.source == "user" else (
            current.confidence if current is not None else saved.confidence
        )
        warning = saved.warning or (current.warning if current is not None else None)
        result[saved.key] = replace(
            saved,
            evidence=evidence,
            confidence=confidence,
            warning=warning,
        )
    return tuple(
        sorted(result.values(), key=lambda item: (item.parent_field, item.child_field))
    )


def perfect_cycle_fields(
    relationships: Iterable[HierarchyRelationship],
) -> tuple[tuple[str, ...], ...]:
    """Return cycles among perfect relationships without rejecting the model."""
    parents: dict[str, set[str]] = {}
    for item in relationships:
        if item.relation == RELATION_PERFECT:
            parents.setdefault(item.child_field, set()).add(item.parent_field)

    cycles: set[tuple[str, ...]] = set()

    def walk(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            index = path.index(node)
            cycle = path[index:] + (node,)
            body = cycle[:-1]
            if body:
                rotations = [body[index:] + body[:index] for index in range(len(body))]
                canonical = min(rotations)
                cycles.add(canonical + (canonical[0],))
            return
        for parent in parents.get(node, ()):
            walk(parent, path + (node,))

    for child in parents:
        walk(child, ())
    return tuple(sorted(cycles))


def relationship_warnings(
    relationships: Iterable[HierarchyRelationship],
) -> tuple[str, ...]:
    """Return user-facing structural warnings without blocking import."""
    items = tuple(relationships)
    warnings = [item.warning for item in items if item.warning]
    for cycle in perfect_cycle_fields(items):
        warnings.append(
            "Perfect structural relationships contain a cycle: " + " -> ".join(cycle)
        )
    return tuple(dict.fromkeys(str(item) for item in warnings if item))


def safe_perfect_relationships(
    relationships: Iterable[HierarchyRelationship],
) -> tuple[HierarchyRelationship, ...]:
    """Return perfect dyads safe to use for grouping/path derivation.

    Edges participating in a perfect cycle are excluded from automatic identity
    and navigation behavior, but remain persisted and visible for user review.
    """
    items = tuple(relationships)
    cycle_edges: set[tuple[str, str]] = set()
    for cycle in perfect_cycle_fields(items):
        for child, parent in zip(cycle, cycle[1:]):
            cycle_edges.add((child, parent))
    return tuple(
        item
        for item in items
        if item.relation == RELATION_PERFECT and item.key not in cycle_edges
    )


def derive_hierarchy_paths(
    relationships: Iterable[HierarchyRelationship],
    *,
    limit: int = 50,
) -> tuple[tuple[str, ...], ...]:
    """Derive broad -> narrow display paths from safe perfect dyads.

    Multiple parents naturally produce multiple valid paths. Sibling fields are
    never forced into a single ordering.
    """
    items = safe_perfect_relationships(relationships)
    children_by_parent: dict[str, set[str]] = {}
    parents: set[str] = set()
    children: set[str] = set()
    for item in items:
        children_by_parent.setdefault(item.parent_field, set()).add(item.child_field)
        parents.add(item.parent_field)
        children.add(item.child_field)
    roots = sorted(parents - children)
    paths: list[tuple[str, ...]] = []

    def descend(node: str, path: tuple[str, ...]) -> None:
        if len(paths) >= limit:
            return
        next_children = sorted(children_by_parent.get(node, ()))
        if not next_children:
            if len(path) > 1:
                paths.append(path)
            return
        for child in next_children:
            descend(child, path + (child,))

    for root in roots:
        descend(root, (root,))
        if len(paths) >= limit:
            break
    return tuple(paths)


def qualified_identity_fields(
    relationships: Iterable[HierarchyRelationship],
) -> tuple[str, ...]:
    """Return fields explicitly required to disambiguate user-reviewed identity."""
    fields: list[str] = []
    safe_keys = {item.key for item in safe_perfect_relationships(relationships)}
    for item in relationships:
        if item.key in safe_keys and item.source == "user":
            fields.extend(item.identity_fields)
    return tuple(dict.fromkeys(field for field in fields if field))
