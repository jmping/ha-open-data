"""Options flow for Open Data dataset entries."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .analyzer import DatasetStructure, build_selectable_records
from .const import (
    CONF_DATASET_KIND,
    CONF_DISPLAY_FIELD,
    CONF_FIELD_ROLES,
    CONF_HIERARCHY_FIELDS,
    CONF_HIERARCHY_SETS,
    CONF_IDENTITY_FIELD,
    CONF_IGNORED_FIELDS,
    CONF_METRIC_FIELDS,
    CONF_PROFILE_ID,
    CONF_RECORD_KEY_FIELDS,
    CONF_RECORD_LABEL_FIELDS,
    CONF_RECORD_STRUCTURE,
    CONF_SELECTED_FIELDS,
    CONF_SELECTED_RECORDS,
    CONF_TIMESTAMP_FIELD,
    CONF_TIMESTAMP_FIELDS,
    CONF_UNIT_KEY_FIELDS,
    CONF_UNIT_LABEL_FIELDS,
)
from .field_roles import (
    FIELD_ROLE_DATA,
    FIELD_ROLE_DESCRIPTIVE,
    FIELD_ROLE_IRRELEVANT,
    FIELD_ROLE_LOCATION,
    FIELD_ROLE_MEASUREMENT_NAME,
    FIELD_ROLE_TIME,
    FIELD_ROLE_UNASSIGNED,
    assignments_from_categories,
    classify_field_roles,
)
from .options_reconciliation import reconcile_options
from .record_structure import (
    build_record_selections,
    build_record_structure,
    load_record_structure,
)

_RECORD_LIMIT = 500
_FIELD_ROLE_CATEGORY_PREFIX = "field_role_fields__"
_FIELD_ROLE_OPTIONS = (
    (FIELD_ROLE_LOCATION, "Location"),
    (FIELD_ROLE_TIME, "Time"),
    (FIELD_ROLE_DATA, "Data / measurement"),
    (FIELD_ROLE_MEASUREMENT_NAME, "Measurement name (long format)"),
    (FIELD_ROLE_DESCRIPTIVE, "Descriptive"),
    (FIELD_ROLE_IRRELEVANT, "Irrelevant"),
)


class OpenDataOptionsFlow(config_entries.OptionsFlow):
    """Choose structural fields first, then records/locations and metrics."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._structure_options: dict[str, Any] = {}

    @staticmethod
    def _fields_selector(values: list[str]) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=value, label=value) for value in values
                ],
                multiple=True,
                mode=SelectSelectorMode.LIST,
                sort=False,
            )
        )

    def _current(self, key: str) -> Any:
        return self._config_entry.options.get(key, self._config_entry.data.get(key))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select structural fields before deriving record choices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            submitted = dict(user_input)
            dataset = self._config_entry.runtime_data.data.dataset
            fields_by_role: dict[str, list[str]] = {}
            for role, _label in _FIELD_ROLE_OPTIONS:
                key = f"{_FIELD_ROLE_CATEGORY_PREFIX}{role}"
                selected = submitted.pop(key, ())
                if isinstance(selected, str):
                    selected = [selected]
                fields_by_role[role] = list(selected or ())
            try:
                submitted[CONF_FIELD_ROLES] = assignments_from_categories(
                    (field.name for field in dataset.fields), fields_by_role
                )
            except ValueError:
                errors["base"] = "invalid_field_roles"
            else:
                self._structure_options = submitted
                return await self.async_step_structure()

        coordinator = self._config_entry.runtime_data
        dataset = coordinator.data.dataset
        ignored = set(self._config_entry.data.get(CONF_IGNORED_FIELDS, ()))
        all_fields = [field.name for field in dataset.fields if field.name not in ignored]
        current_roles = self._current(CONF_FIELD_ROLES) or {}
        if not current_roles:
            role_rows = (
                list(coordinator.data.records.values())
                if coordinator.data.records
                else [coordinator.data.values]
            )
            structural_fields = {
                self._current(CONF_IDENTITY_FIELD),
                self._current(CONF_DISPLAY_FIELD),
                *self._config_entry.data.get("location_fields", ()),
            }
            structural_fields.discard(None)
            current_roles = classify_field_roles(
                all_fields,
                role_rows,
                configured_metrics=self._config_entry.data.get(
                    CONF_METRIC_FIELDS, ()
                ),
                structural_fields=structural_fields,
                timestamp_fields=self._config_entry.data.get(
                    CONF_TIMESTAMP_FIELDS, ()
                ),
                ignored_fields=ignored,
            ).as_assignments()

        schema: dict[Any, Any] = {}
        identity = self._current(CONF_IDENTITY_FIELD)
        role_fields = all_fields
        for role, _label in _FIELD_ROLE_OPTIONS:
            role_key = f"{_FIELD_ROLE_CATEGORY_PREFIX}{role}"
            schema[vol.Optional(
                role_key,
                default=[
                    field for field in role_fields
                    if current_roles.get(field, FIELD_ROLE_UNASSIGNED) == role
                ],
            )] = self._fields_selector(role_fields)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "kind": self._config_entry.data.get(CONF_DATASET_KIND, "table"),
                "identity": identity or "none",
            },
        )

    async def async_step_structure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Combine reviewed fields into nested unit and observation identities."""
        field_roles = self._structure_options[CONF_FIELD_ROLES]
        active_fields = {
            field
            for field, role in field_roles.items()
            if role not in {FIELD_ROLE_IRRELEVANT, FIELD_ROLE_UNASSIGNED}
        }
        if user_input is not None:
            submitted = dict(user_input)
            hierarchy_sets = tuple(
                tuple(submitted.pop(key, ()) or ())
                for key in (
                    CONF_HIERARCHY_FIELDS,
                    f"{CONF_HIERARCHY_FIELDS}__2",
                    f"{CONF_HIERARCHY_FIELDS}__3",
                )
                if submitted.get(key)
            )
            submitted[CONF_HIERARCHY_SETS] = [list(path) for path in hierarchy_sets]
            submitted[CONF_HIERARCHY_FIELDS] = list(
                dict.fromkeys(field for path in hierarchy_sets for field in path)
            )
            submitted[CONF_RECORD_STRUCTURE] = build_record_structure(
                unit_key_fields=submitted.get(CONF_UNIT_KEY_FIELDS, ()),
                unit_label_fields=submitted.get(CONF_UNIT_LABEL_FIELDS, ()),
                record_key_fields=submitted.get(CONF_RECORD_KEY_FIELDS, ()),
                record_label_fields=submitted.get(CONF_RECORD_LABEL_FIELDS, ()),
                hierarchy_paths=hierarchy_sets,
                allowed_fields=active_fields,
            ).as_dict()
            self._structure_options.update(submitted)
            return await self.async_step_records()

        location_fields = [
            field for field in active_fields
            if field_roles.get(field) == FIELD_ROLE_LOCATION
        ]
        label_fields = [
            field for field in active_fields
            if field_roles.get(field) in {
                FIELD_ROLE_LOCATION,
                FIELD_ROLE_MEASUREMENT_NAME,
                FIELD_ROLE_DESCRIPTIVE,
            }
        ]
        unit_fields = list(label_fields)
        record_fields = [
            field for field in active_fields
            if field_roles.get(field) in {
                FIELD_ROLE_LOCATION,
                FIELD_ROLE_TIME,
                FIELD_ROLE_MEASUREMENT_NAME,
                FIELD_ROLE_DESCRIPTIVE,
            }
        ]
        identity = self._structure_options.get(CONF_IDENTITY_FIELD)
        display = self._structure_options.get(CONF_DISPLAY_FIELD)
        current_unit_keys = self._current(CONF_UNIT_KEY_FIELDS) or (
            [identity] if identity in active_fields else location_fields
        )
        current_unit_labels = self._current(CONF_UNIT_LABEL_FIELDS) or (
            [display] if display in active_fields else []
        )
        current_unit_keys = [
            field for field in current_unit_keys if field in unit_fields
        ]
        current_unit_labels = [
            field for field in current_unit_labels if field in label_fields
        ]
        current_record_keys = self._current(CONF_RECORD_KEY_FIELDS) or list(
            dict.fromkeys((*current_unit_keys, *(
                field for field in record_fields
                if field_roles.get(field) == FIELD_ROLE_TIME
            )))
        )
        current_record_keys = [
            field for field in current_record_keys if field in record_fields
        ]
        current_record_labels = self._current(CONF_RECORD_LABEL_FIELDS) or list(
            current_unit_labels
        )
        current_record_labels = [
            field for field in current_record_labels if field in record_fields
        ]
        current_hierarchy_sets = self._current(CONF_HIERARCHY_SETS) or (
            self._current(CONF_HIERARCHY_FIELDS) or (),
        )
        current_hierarchy_sets = tuple(
            tuple(field for field in path if field in label_fields)
            for path in current_hierarchy_sets
            if isinstance(path, (list, tuple))
        )
        schema: dict[Any, Any] = {}
        for index, key in enumerate(
            (
                CONF_HIERARCHY_FIELDS,
                f"{CONF_HIERARCHY_FIELDS}__2",
                f"{CONF_HIERARCHY_FIELDS}__3",
            )
        ):
            schema[vol.Optional(
                key,
                default=list(current_hierarchy_sets[index])
                if index < len(current_hierarchy_sets)
                else [],
            )] = self._fields_selector(label_fields)
        schema.update({
            vol.Optional(
                CONF_UNIT_KEY_FIELDS, default=list(current_unit_keys)
            ): self._fields_selector(unit_fields),
            vol.Optional(
                CONF_UNIT_LABEL_FIELDS, default=list(current_unit_labels)
            ): self._fields_selector(label_fields),
            vol.Optional(
                CONF_RECORD_KEY_FIELDS, default=list(current_record_keys)
            ): self._fields_selector(record_fields),
            vol.Optional(
                CONF_RECORD_LABEL_FIELDS, default=list(current_record_labels)
            ): self._fields_selector(record_fields),
        })
        return self.async_show_form(
            step_id="structure",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "kind": self._config_entry.data.get(CONF_DATASET_KIND, "table"),
                "identity": identity or "none",
            },
        )

    async def async_step_records(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Build record choices from the just-selected structural fields."""
        if user_input is not None:
            options = {**self._structure_options, **user_input}
            return self.async_create_entry(title="", data=options)

        coordinator = self._config_entry.runtime_data
        dataset = coordinator.data.dataset
        field_roles = self._structure_options.get(
            CONF_FIELD_ROLES,
            self._current(CONF_FIELD_ROLES) or {},
        )
        ignored = {
            field for field, role in field_roles.items()
            if role in {FIELD_ROLE_IRRELEVANT, FIELD_ROLE_UNASSIGNED}
        }
        metrics = {
            field for field, role in field_roles.items() if role == FIELD_ROLE_DATA
        }
        choices = {
            field.name: field.label
            for field in dataset.fields
            if field.name in metrics
        }
        fields_were_configured = (
            CONF_SELECTED_FIELDS in self._config_entry.options
            or CONF_SELECTED_FIELDS in self._config_entry.data
        )
        raw_fields = self._current(CONF_SELECTED_FIELDS)
        schema: dict[Any, Any] = {}

        identity = self._structure_options.get(CONF_IDENTITY_FIELD)
        display = self._structure_options.get(CONF_DISPLAY_FIELD)
        timestamp = self._structure_options.get(CONF_TIMESTAMP_FIELD)
        hierarchy_fields = tuple(
            self._structure_options.get(
                CONF_HIERARCHY_FIELDS,
                self._config_entry.data.get(CONF_HIERARCHY_FIELDS, ()),
            )
        )
        persisted_structure = load_record_structure(
            self._structure_options.get(CONF_RECORD_STRUCTURE)
        )
        unit_key_fields = persisted_structure.unit_key_fields
        unit_label_fields = persisted_structure.unit_label_fields
        query_identity = unit_key_fields[0] if unit_key_fields else identity
        if query_identity:
            extra_fields = tuple(
                dict.fromkeys(
                    (
                        *unit_key_fields[1:],
                        *unit_label_fields,
                        *hierarchy_fields,
                    )
                )
            )
            rows = await coordinator.provider.async_distinct_rows(
                dataset.dataset_id,
                dataset.resource_id,
                query_identity,
                None if unit_key_fields else display,
                extra_fields,
                limit=_RECORD_LIMIT,
            )
            legacy_structure = DatasetStructure(
                kind=self._config_entry.data.get(CONF_DATASET_KIND, "records"),
                profile_id=self._config_entry.data.get(CONF_PROFILE_ID),
                confidence=1.0,
                identity_field=identity,
                display_field=display,
                timestamp_field=timestamp,
                geometry_field=None,
                geometry_type=None,
                hierarchy_fields=hierarchy_fields,
                metric_fields=tuple(metrics),
                ignored_fields=tuple(ignored),
            )
            if unit_key_fields:
                records = build_record_selections(rows, persisted_structure)
            else:
                records = build_selectable_records(rows, legacy_structure)
            record_choices = {record.value: record.label for record in records}
            if record_choices:
                records_were_configured = (
                    CONF_SELECTED_RECORDS in self._config_entry.options
                    or CONF_SELECTED_RECORDS in self._config_entry.data
                )
                reconciled = reconcile_options(
                    raw_records=self._current(CONF_SELECTED_RECORDS),
                    records_were_configured=records_were_configured,
                    available_records=records,
                    unit_key_fields=(unit_key_fields or (identity,)),
                    raw_fields=raw_fields,
                    fields_were_configured=fields_were_configured,
                    available_fields=choices,
                )
                schema[
                    vol.Optional(
                        CONF_SELECTED_RECORDS,
                        default=list(reconciled.selected_records),
                    )
                ] = cv.multi_select(record_choices)

        reconciled_fields = reconcile_options(
            raw_records=(),
            records_were_configured=True,
            available_records=(),
            unit_key_fields=(),
            raw_fields=raw_fields,
            fields_were_configured=fields_were_configured,
            available_fields=choices,
        ).selected_fields
        schema[
            vol.Optional(CONF_SELECTED_FIELDS, default=list(reconciled_fields))
        ] = cv.multi_select(choices)

        return self.async_show_form(
            step_id="records",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "kind": self._config_entry.data.get(CONF_DATASET_KIND, "table"),
                "identity": identity or "none",
            },
        )
