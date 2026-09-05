"""Post-import options menu with editable structural field dyads."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_FIELD_ROLES,
    CONF_HIERARCHY_FIELDS,
    CONF_HIERARCHY_RELATIONSHIPS,
    CONF_HIERARCHY_SETS,
    CONF_IDENTITY_FIELD,
    CONF_IDENTITY_FIELDS,
    CONF_RECORD_KEY_FIELDS,
    CONF_RECORD_LABEL_FIELDS,
    CONF_RECORD_STRUCTURE,
    CONF_UNIT_KEY_FIELDS,
    CONF_UNIT_LABEL_FIELDS,
)
from .field_roles import (
    FIELD_ROLE_DESCRIPTIVE,
    FIELD_ROLE_LOCATION,
    FIELD_ROLE_MEASUREMENT_NAME,
)
from .hierarchy_relationships import (
    RELATION_IMPERFECT,
    RELATION_KINDS,
    RELATION_NONE,
    RELATION_PERFECT,
    RELATION_UNKNOWN,
    HierarchyRelationship,
    analyze_relationship,
    apply_user_relationship,
    derive_hierarchy_paths,
    infer_relationships,
    load_relationships,
    merge_relationships,
    qualified_identity_fields,
    relationship_warnings,
    relationship_candidate_fields,
    relationships_from_paths,
)
from .options_flow import OpenDataOptionsFlow
from .record_structure import build_record_structure, load_record_structure

CONF_MANUAL_CHILD = "manual_relationship_child"
CONF_MANUAL_PARENT = "manual_relationship_parent"
CONF_MANUAL_RELATION = "manual_relationship_type"
_DYAD_GROUP_PREFIX = "relationship_keys__"
_DYAD_SEPARATOR = "\u001f"
_MAX_EDITABLE_DYADS = 40

_RELATION_LABELS = {
    RELATION_PERFECT: "Perfect nesting — each child belongs to one parent",
    RELATION_IMPERFECT: "Imperfect / overlapping relationship",
    RELATION_NONE: "No structural relationship",
    RELATION_UNKNOWN: "Unknown / do not assume",
}


class OpenDataDyadOptionsFlow(OpenDataOptionsFlow):
    """Let users improve one aspect of an import without replaying onboarding."""

    @staticmethod
    def _relation_selector() -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=value, label=_RELATION_LABELS[value])
                    for value in RELATION_KINDS
                ],
                multiple=False,
                mode=SelectSelectorMode.DROPDOWN,
                sort=False,
            )
        )

    @staticmethod
    def _field_selector(fields: list[str]) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=field, label=field) for field in fields],
                multiple=False,
                mode=SelectSelectorMode.DROPDOWN,
                sort=False,
            )
        )

    @staticmethod
    def _dyad_value(item: HierarchyRelationship) -> str:
        return f"{item.child_field}{_DYAD_SEPARATOR}{item.parent_field}"

    @staticmethod
    def _dyad_key(value: str) -> tuple[str, str] | None:
        if _DYAD_SEPARATOR not in value:
            return None
        child, parent = value.split(_DYAD_SEPARATOR, 1)
        if not child or not parent or child == parent:
            return None
        return (child, parent)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Offer independent post-import adjustments."""
        return self.async_show_menu(
            step_id="menu",
            menu_options=[
                "records",
                "semantics",
                "temporal",
                "relationships",
                "advanced",
            ],
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter the original full structural review only when requested."""
        return await super().async_step_init(user_input)

    async def async_step_records(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Adjust records/measures and save immediately."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self._config_entry.options, **dict(user_input)},
            )
        return await super().async_step_records(None)

    def _candidate_fields(self) -> list[str]:
        dataset = self._config_entry.runtime_data.data.dataset
        roles = self._current(CONF_FIELD_ROLES) or {}
        structural_roles = {
            FIELD_ROLE_LOCATION,
            FIELD_ROLE_MEASUREMENT_NAME,
            FIELD_ROLE_DESCRIPTIVE,
        }
        candidates = [
            field.name
            for field in dataset.fields
            if roles.get(field.name) in structural_roles
        ]
        candidates.extend(self._current(CONF_IDENTITY_FIELDS) or ())
        identity = self._current(CONF_IDENTITY_FIELD)
        if identity:
            candidates.append(identity)
        return list(dict.fromkeys(field for field in candidates if field))

    def _evidence_rows(self) -> list[dict[str, Any]]:
        snapshot = self._config_entry.runtime_data.data
        if snapshot.records:
            return [dict(row) for row in snapshot.records.values()]
        if snapshot.values:
            return [dict(snapshot.values)]
        return []

    def _current_relationships(self) -> tuple[HierarchyRelationship, ...]:
        persisted = load_relationships(self._current(CONF_HIERARCHY_RELATIONSHIPS))
        if not persisted:
            raw_paths = self._current(CONF_HIERARCHY_SETS) or ()
            if not raw_paths:
                flat = tuple(self._current(CONF_HIERARCHY_FIELDS) or ())
                raw_paths = (flat,) if flat else ()
            persisted = relationships_from_paths(raw_paths)
        fields = self._candidate_fields()
        rows = self._evidence_rows()
        roles = self._current(CONF_FIELD_ROLES) or {}
        inference_fields = relationship_candidate_fields(
            rows,
            identity_fields=(
                *(self._current(CONF_IDENTITY_FIELDS) or ()),
                self._current(CONF_IDENTITY_FIELD),
            ),
            location_fields=(
                field
                for field in fields
                if roles.get(field) == FIELD_ROLE_LOCATION
            ),
            hierarchy_fields=(self._current(CONF_HIERARCHY_FIELDS) or ()),
        )
        inferred = (
            infer_relationships(rows, inference_fields)
            if rows and len(inference_fields) > 1
            else ()
        )
        return merge_relationships(inferred, persisted)

    @staticmethod
    def _dyad_label(item: HierarchyRelationship) -> str:
        evidence = item.evidence
        suffix = (
            f"{evidence.observed_children} child values; "
            f"{evidence.multi_parent_children} conflicts; "
            f"{item.confidence:.0%} confidence"
            if evidence.observed_children
            else "legacy/user relationship; no current bounded evidence"
        )
        return f"{item.child_field} → {item.parent_field} · {suffix}"

    def _persist_relationships(
        self, relationships: tuple[HierarchyRelationship, ...]
    ) -> dict[str, Any]:
        """Persist canonical dyads and derived compatibility paths/identity."""
        options = dict(self._config_entry.options)
        options[CONF_HIERARCHY_RELATIONSHIPS] = [
            item.as_dict() for item in relationships
        ]

        paths = derive_hierarchy_paths(relationships)
        options[CONF_HIERARCHY_SETS] = [list(path) for path in paths]
        options[CONF_HIERARCHY_FIELDS] = list(
            dict.fromkeys(field for path in paths for field in path)
        )

        identity_hints = qualified_identity_fields(relationships)
        existing_structure = load_record_structure(self._current(CONF_RECORD_STRUCTURE))
        configured_unit_keys = tuple(self._current(CONF_UNIT_KEY_FIELDS) or ())
        if not configured_unit_keys:
            configured_identity = self._current(CONF_IDENTITY_FIELD)
            configured_unit_keys = (
                (configured_identity,) if configured_identity else ()
            )
        unit_keys = tuple(dict.fromkeys((*configured_unit_keys, *identity_hints)))
        unit_labels = tuple(self._current(CONF_UNIT_LABEL_FIELDS) or ())
        record_keys = tuple(self._current(CONF_RECORD_KEY_FIELDS) or ())
        record_labels = tuple(self._current(CONF_RECORD_LABEL_FIELDS) or ())
        if not record_keys:
            record_keys = existing_structure.record_key_fields
        if not record_labels:
            record_labels = existing_structure.record_label_fields

        all_fields = [
            field.name for field in self._config_entry.runtime_data.data.dataset.fields
        ]
        options[CONF_UNIT_KEY_FIELDS] = list(unit_keys)
        options[CONF_RECORD_STRUCTURE] = build_record_structure(
            unit_key_fields=unit_keys,
            unit_label_fields=unit_labels,
            record_key_fields=record_keys,
            record_label_fields=record_labels,
            hierarchy_paths=paths,
            allowed_fields=all_fields,
        ).as_dict()
        return options

    async def async_step_relationships(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Review known child -> parent dyads without forcing one hierarchy tree."""
        fields = self._candidate_fields()
        current = self._current_relationships()
        editable = current[:_MAX_EDITABLE_DYADS]
        by_key = {item.key: item for item in current}
        errors: dict[str, str] = {}

        if user_input is not None:
            submitted = dict(user_input)
            stable_ids = tuple(self._current(CONF_IDENTITY_FIELDS) or ())
            identity = self._current(CONF_IDENTITY_FIELD)
            if identity:
                stable_ids = tuple(dict.fromkeys((*stable_ids, identity)))

            assignments: dict[tuple[str, str], str] = {}
            for relation in RELATION_KINDS:
                selected = submitted.pop(f"{_DYAD_GROUP_PREFIX}{relation}", ()) or ()
                if isinstance(selected, str):
                    selected = [selected]
                for raw_value in selected:
                    key = self._dyad_key(str(raw_value))
                    if key is None or key not in {item.key for item in editable}:
                        errors["base"] = "invalid_relationship"
                        continue
                    if key in assignments:
                        errors["base"] = "invalid_relationship"
                        continue
                    assignments[key] = relation

            updated: dict[tuple[str, str], HierarchyRelationship] = dict(by_key)
            for item in editable:
                relation = assignments.get(item.key, RELATION_UNKNOWN)
                updated[item.key] = apply_user_relationship(
                    item,
                    relation,
                    stable_identity_fields=stable_ids,
                )

            child = str(submitted.pop(CONF_MANUAL_CHILD, "") or "")
            parent = str(submitted.pop(CONF_MANUAL_PARENT, "") or "")
            relation = str(
                submitted.pop(CONF_MANUAL_RELATION, RELATION_UNKNOWN)
                or RELATION_UNKNOWN
            )
            if child or parent:
                if not child or not parent or child == parent:
                    errors["base"] = "invalid_relationship"
                elif child not in fields or parent not in fields:
                    errors["base"] = "invalid_relationship"
                else:
                    evidence = analyze_relationship(self._evidence_rows(), child, parent)
                    updated[evidence.key] = apply_user_relationship(
                        evidence,
                        relation,
                        stable_identity_fields=stable_ids,
                    )

            if not errors:
                relationships = tuple(
                    sorted(
                        updated.values(),
                        key=lambda item: (
                            item.parent_field.casefold(),
                            item.child_field.casefold(),
                        ),
                    )
                )
                return self.async_create_entry(
                    title="", data=self._persist_relationships(relationships)
                )

        choices = [
            SelectOptionDict(value=self._dyad_value(item), label=self._dyad_label(item))
            for item in editable
        ]
        schema: dict[Any, Any] = {}
        if choices:
            selector = SelectSelector(
                SelectSelectorConfig(
                    options=choices,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    sort=False,
                )
            )
            for relation in RELATION_KINDS:
                schema[
                    vol.Optional(
                        f"{_DYAD_GROUP_PREFIX}{relation}",
                        default=[
                            self._dyad_value(item)
                            for item in editable
                            if item.relation == relation
                        ],
                    )
                ] = selector

        if fields:
            schema[vol.Optional(CONF_MANUAL_CHILD, default="")] = self._field_selector(
                fields
            )
            schema[vol.Optional(CONF_MANUAL_PARENT, default="")] = self._field_selector(
                fields
            )
            schema[
                vol.Optional(CONF_MANUAL_RELATION, default=RELATION_UNKNOWN)
            ] = self._relation_selector()

        warnings = relationship_warnings(current)
        warning_text = " | ".join(warnings[:4]) if warnings else "none"
        hidden = max(0, len(current) - len(editable))
        return self.async_show_form(
            step_id="relationships",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "relationship_count": str(len(current)),
                "hidden_count": str(hidden),
                "warnings": warning_text,
            },
        )
