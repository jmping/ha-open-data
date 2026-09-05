"""Options flow for Open Data dataset entries."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

from .analysis_api import build_selectable_records
from .analyzer import DatasetStructure
from .const import (
    CONF_DATASET_KIND,
    CONF_DISPLAY_FIELD,
    CONF_FIELD_ROLES,
    CONF_HIERARCHY_FIELDS,
    CONF_HIERARCHY_SETS,
    CONF_IDENTITY_FIELD,
    CONF_IGNORED_FIELDS,
    CONF_MEASURE_FRESHNESS,
    CONF_MEASURE_KINDS,
    CONF_METRIC_FIELDS,
    CONF_PROFILE_ID,
    CONF_RECORD_KEY_FIELDS,
    CONF_RECORD_LABEL_FIELDS,
    CONF_RECORD_STRUCTURE,
    CONF_SELECTED_FIELDS,
    CONF_SELECTED_RECORDS,
    CONF_TEMPORAL_FIELD_ROLES,
    CONF_TEMPORAL_PLAN,
    CONF_TIMESTAMP_FIELD,
    CONF_TIMEZONE,
    CONF_TIMEZONE_SOURCE,
    CONF_UNIT_KEY_FIELDS,
    CONF_UNIT_LABEL_FIELDS,
)
from .coordinate_fields import coordinate_candidate_fields
from .data_semantics import (
    MEASURE_KINDS,
    MEASURE_KIND_CATEGORY,
    MEASURE_KIND_CUMULATIVE,
    MEASURE_KIND_DURATION,
    MEASURE_KIND_EVENT_COUNT,
    MEASURE_KIND_EVENT_OCCURRENCE,
    MEASURE_KIND_INSTANTANEOUS,
    MEASURE_KIND_INTERVAL_AMOUNT,
    MEASURE_KIND_RATE,
    MEASURE_KIND_STATUS,
    MEASURE_KIND_UNKNOWN,
    TIME_ROLES,
    TIME_ROLE_AS_OF,
    TIME_ROLE_END,
    TIME_ROLE_EVENT,
    TIME_ROLE_OBSERVATION,
    TIME_ROLE_OTHER,
    TIME_ROLE_PREVIOUS_EVENT,
    TIME_ROLE_PUBLISHED,
    TIME_ROLE_START,
    TIME_ROLE_UPDATED,
    infer_measure_kind,
    infer_time_role,
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
from .location_ranking import rank_location_rows
from .options_reconciliation import reconcile_options
from .record_structure import (
    build_record_selections,
    build_record_structure,
    load_record_structure,
)

_RECORD_LIMIT = 200
CONF_TEMPORAL_MODE = "temporal_mode"
_TEMPORAL_AUTO = "automatic"
_TEMPORAL_FIELD = "single_field"
_FIELD_ROLE_CATEGORY_PREFIX = "field_role_fields__"
_TIME_ROLE_CATEGORY_PREFIX = "time_role_fields__"
_MEASURE_KIND_CATEGORY_PREFIX = "measure_kind_fields__"
_FIELD_ROLE_OPTIONS = (
    (FIELD_ROLE_LOCATION, "Location"),
    (FIELD_ROLE_TIME, "Time"),
    (FIELD_ROLE_DATA, "Data / measurement"),
    (FIELD_ROLE_MEASUREMENT_NAME, "Measurement name (long format)"),
    (FIELD_ROLE_DESCRIPTIVE, "Descriptive"),
    (FIELD_ROLE_IRRELEVANT, "Irrelevant"),
)
_TIME_ROLE_OPTIONS = (
    (TIME_ROLE_OBSERVATION, "Observation / measurement time"),
    (TIME_ROLE_EVENT, "Event occurrence time"),
    (TIME_ROLE_AS_OF, "As-of / effective time"),
    (TIME_ROLE_PUBLISHED, "Publication / issue time"),
    (TIME_ROLE_UPDATED, "Source update time"),
    (TIME_ROLE_START, "Start / onset time"),
    (TIME_ROLE_END, "End / expiry time"),
    (TIME_ROLE_PREVIOUS_EVENT, "Previous / prior event time"),
    (TIME_ROLE_OTHER, "Other time"),
)
_MEASURE_KIND_OPTIONS = (
    (MEASURE_KIND_INSTANTANEOUS, "Current / instantaneous measure"),
    (MEASURE_KIND_CUMULATIVE, "Cumulative counter / total"),
    (MEASURE_KIND_INTERVAL_AMOUNT, "Amount or volume during an interval"),
    (MEASURE_KIND_DURATION, "Elapsed time / duration"),
    (MEASURE_KIND_EVENT_COUNT, "Cumulative event count"),
    (MEASURE_KIND_EVENT_OCCURRENCE, "Event occurrence / indicator"),
    (MEASURE_KIND_RATE, "Rate / speed / flow"),
    (MEASURE_KIND_STATUS, "Status / state"),
    (MEASURE_KIND_CATEGORY, "Category / nominal value"),
    (MEASURE_KIND_UNKNOWN, "Unknown / do not assume behavior"),
)


class OpenDataOptionsFlow(config_entries.OptionsFlow):
    """Review inferred import choices, with advanced structure controls available."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._structure_options: dict[str, Any] = {}

    @staticmethod
    def _fields_selector(values: list[str]) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=value, label=value) for value in values],
                multiple=True,
                mode=SelectSelectorMode.LIST,
                sort=False,
            )
        )

    @staticmethod
    def _one_field_selector(values: list[str]) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=value, label=value) for value in values],
                multiple=False,
                mode=SelectSelectorMode.DROPDOWN,
                sort=False,
            )
        )

    def _current(self, key: str) -> Any:
        if key in self._structure_options:
            return self._structure_options[key]
        return self._config_entry.options.get(key, self._config_entry.data.get(key))

    def _freshness_label(self, field: str, label: str) -> str:
        profile = (self._config_entry.data.get(CONF_MEASURE_FRESHNESS) or {}).get(field) or {}
        status = profile.get("status")
        latest = profile.get("latest_observation_at")
        cadence = profile.get("cadence_seconds")
        parts = [label]
        if status:
            parts.append(str(status))
        if latest:
            parts.append(f"latest {latest}")
        if cadence:
            seconds = float(cadence)
            if seconds < 3600:
                parts.append(f"~{max(1, round(seconds / 60))}m cadence")
            elif seconds < 86400:
                parts.append(f"~{max(1, round(seconds / 3600))}h cadence")
            else:
                parts.append(f"~{max(1, round(seconds / 86400))}d cadence")
        elif status == "unknown":
            parts.append("recency unknown")
        return " · ".join(parts)

    def _review_placeholders(
        self, record_count: int = 0, *, high_cardinality: bool = False
    ) -> dict[str, str]:
        temporal = self._current(CONF_TEMPORAL_PLAN) or {}
        plan = temporal.get("plan") or {}
        status = temporal.get("status") or "unknown"
        strategy = plan.get("strategy") or "not resolved"
        confidence = plan.get("confidence")
        confidence_label = (
            f"{float(confidence):.0%}" if confidence is not None else "unknown"
        )
        timezone = self._current(CONF_TIMEZONE) or "unknown"
        timezone_source = self._current(CONF_TIMEZONE_SOURCE) or "unknown"
        selected_fields = self._current(CONF_SELECTED_FIELDS)
        metric_count = len(selected_fields or ())
        entity_estimate = metric_count * max(record_count, 1)
        stale = sum(
            1
            for value in (self._config_entry.data.get(CONF_MEASURE_FRESHNESS) or {}).values()
            if isinstance(value, dict) and value.get("status") == "stale"
        )
        return {
            "temporal_status": str(status),
            "timestamp_strategy": str(strategy),
            "timestamp_confidence": confidence_label,
            "timezone": str(timezone),
            "timezone_source": str(timezone_source),
            "stale_count": str(stale),
            "record_count": f"{record_count}+" if high_cardinality else str(record_count),
            "entity_estimate": "suppressed" if high_cardinality else str(entity_estimate),
            "record_mode": (
                "high-cardinality; flat record selection is disabled"
                if high_cardinality
                else "bounded selectable records"
            ),
        }

    @staticmethod
    def _semantic_assignments(
        fields: list[str],
        submitted: dict[str, Any],
        *,
        prefix: str,
        categories: tuple[str, ...],
    ) -> dict[str, str]:
        assignments: dict[str, str] = {}
        allowed = set(fields)
        for category in categories:
            selected = submitted.pop(f"{prefix}{category}", ()) or ()
            if isinstance(selected, str):
                selected = [selected]
            for field in selected:
                if field not in allowed or field in assignments:
                    raise ValueError("semantic field categories must be disjoint")
                assignments[field] = category
        return assignments

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select structural fields before deriving record choices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            submitted = dict(user_input)
            dataset = self._config_entry.runtime_data.data.dataset
            fields_by_role: dict[str, list[str]] = {}
            for role, _label in _FIELD_ROLE_OPTIONS:
                selected = submitted.pop(f"{_FIELD_ROLE_CATEGORY_PREFIX}{role}", ())
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
                configured_metrics=self._config_entry.data.get(CONF_METRIC_FIELDS, ()),
                structural_fields=structural_fields,
                timestamp_fields=self._config_entry.data.get("timestamp_fields", ()),
                ignored_fields=ignored,
            ).as_assignments()

        schema: dict[Any, Any] = {}
        for role, _label in _FIELD_ROLE_OPTIONS:
            schema[
                vol.Optional(
                    f"{_FIELD_ROLE_CATEGORY_PREFIX}{role}",
                    default=[
                        field
                        for field in all_fields
                        if current_roles.get(field, FIELD_ROLE_UNASSIGNED) == role
                    ],
                )
            ] = self._fields_selector(all_fields)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "kind": self._config_entry.data.get(CONF_DATASET_KIND, "table"),
                "identity": self._current(CONF_IDENTITY_FIELD) or "none",
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
            field
            for field in active_fields
            if field_roles.get(field) == FIELD_ROLE_LOCATION
        ]
        label_fields = [
            field
            for field in active_fields
            if field_roles.get(field)
            in {
                FIELD_ROLE_LOCATION,
                FIELD_ROLE_MEASUREMENT_NAME,
                FIELD_ROLE_DESCRIPTIVE,
            }
        ]
        unit_fields = list(label_fields)
        record_fields = [
            field
            for field in active_fields
            if field_roles.get(field)
            in {
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
        current_unit_keys = [field for field in current_unit_keys if field in unit_fields]
        current_unit_labels = [
            field for field in current_unit_labels if field in label_fields
        ]
        current_record_keys = self._current(CONF_RECORD_KEY_FIELDS) or list(
            dict.fromkeys(
                (
                    *current_unit_keys,
                    *(
                        field
                        for field in record_fields
                        if field_roles.get(field) == FIELD_ROLE_TIME
                    ),
                )
            )
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
            schema[
                vol.Optional(
                    key,
                    default=list(current_hierarchy_sets[index])
                    if index < len(current_hierarchy_sets)
                    else [],
                )
            ] = self._fields_selector(label_fields)
        schema.update(
            {
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
            }
        )
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
        """Review bounded records and freshness-aware metric choices."""
        if user_input is not None:
            self._structure_options.update(dict(user_input))
            return await self.async_step_semantics()

        coordinator = self._config_entry.runtime_data
        dataset = coordinator.data.dataset
        field_roles = self._structure_options.get(
            CONF_FIELD_ROLES, self._current(CONF_FIELD_ROLES) or {}
        )
        ignored = {
            field
            for field, role in field_roles.items()
            if role in {FIELD_ROLE_IRRELEVANT, FIELD_ROLE_UNASSIGNED}
        }
        metrics = {
            field for field, role in field_roles.items() if role == FIELD_ROLE_DATA
        }
        choices = {
            field.name: self._freshness_label(field.name, field.label)
            for field in dataset.fields
            if field.name in metrics
        }
        fields_were_configured = (
            CONF_SELECTED_FIELDS in self._config_entry.options
            or CONF_SELECTED_FIELDS in self._config_entry.data
        )
        raw_fields = self._current(CONF_SELECTED_FIELDS)
        schema: dict[Any, Any] = {}
        record_count = 0
        high_cardinality = False

        identity = self._structure_options.get(CONF_IDENTITY_FIELD) or self._current(
            CONF_IDENTITY_FIELD
        )
        display = self._structure_options.get(CONF_DISPLAY_FIELD) or self._current(
            CONF_DISPLAY_FIELD
        )
        timestamp = self._structure_options.get(CONF_TIMESTAMP_FIELD) or self._current(
            CONF_TIMESTAMP_FIELD
        )
        hierarchy_fields = tuple(
            self._structure_options.get(
                CONF_HIERARCHY_FIELDS,
                self._config_entry.data.get(CONF_HIERARCHY_FIELDS, ()),
            )
        )
        persisted_structure = load_record_structure(
            self._structure_options.get(CONF_RECORD_STRUCTURE)
            or self._current(CONF_RECORD_STRUCTURE)
        )
        unit_key_fields = persisted_structure.unit_key_fields
        unit_label_fields = persisted_structure.unit_label_fields
        query_identity = unit_key_fields[0] if unit_key_fields else identity
        if query_identity:
            coordinate_fields = coordinate_candidate_fields(
                field.name for field in dataset.fields
            )
            extra_fields = tuple(
                dict.fromkeys(
                    (
                        *unit_key_fields[1:],
                        *unit_label_fields,
                        *hierarchy_fields,
                        *coordinate_fields,
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
            high_cardinality = len(rows) >= _RECORD_LIMIT
            rows = rank_location_rows(
                rows,
                home_latitude=self.hass.config.latitude,
                home_longitude=self.hass.config.longitude,
                label_fields=tuple(
                    dict.fromkeys(
                        (*unit_label_fields, *((display,) if display else ()))
                    )
                ),
                hierarchy_fields=hierarchy_fields,
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
            records = (
                build_record_selections(rows, persisted_structure)
                if unit_key_fields
                else build_selectable_records(rows, legacy_structure)
            )
            record_choices = {record.value: record.label for record in records}
            record_count = len(record_choices)
            if record_choices and not high_cardinality:
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
            elif high_cardinality:
                self._structure_options[CONF_SELECTED_RECORDS] = []

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
                **self._review_placeholders(
                    record_count, high_cardinality=high_cardinality
                ),
            },
        )

    async def async_step_semantics(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Review what each clock and measurement means before applying HA semantics."""
        errors: dict[str, str] = {}
        dataset = self._config_entry.runtime_data.data.dataset
        labels = {field.name: field.label for field in dataset.fields}
        field_roles = self._structure_options.get(
            CONF_FIELD_ROLES, self._current(CONF_FIELD_ROLES) or {}
        )
        time_fields = [
            field.name
            for field in dataset.fields
            if field_roles.get(field.name) == FIELD_ROLE_TIME
        ]
        selected_fields = list(self._current(CONF_SELECTED_FIELDS) or ())
        metric_fields = [
            field.name
            for field in dataset.fields
            if field.name in selected_fields
            and field_roles.get(field.name) == FIELD_ROLE_DATA
        ]

        existing_time_roles = dict(self._current(CONF_TEMPORAL_FIELD_ROLES) or {})
        for field in time_fields:
            existing_time_roles.setdefault(
                field, infer_time_role(field, labels.get(field))
            )
        existing_measure_kinds = dict(self._current(CONF_MEASURE_KINDS) or {})
        for field in metric_fields:
            existing_measure_kinds.setdefault(
                field, infer_measure_kind(field, labels.get(field))
            )

        if user_input is not None:
            submitted = dict(user_input)
            primary_timestamp = str(submitted.pop(CONF_TIMESTAMP_FIELD, "") or "")
            try:
                time_roles = self._semantic_assignments(
                    time_fields,
                    submitted,
                    prefix=_TIME_ROLE_CATEGORY_PREFIX,
                    categories=TIME_ROLES,
                )
                measure_kinds = self._semantic_assignments(
                    metric_fields,
                    submitted,
                    prefix=_MEASURE_KIND_CATEGORY_PREFIX,
                    categories=MEASURE_KINDS,
                )
            except ValueError:
                errors["base"] = "invalid_semantics"
            else:
                for field in time_fields:
                    time_roles.setdefault(field, TIME_ROLE_OTHER)
                for field in metric_fields:
                    measure_kinds.setdefault(field, MEASURE_KIND_UNKNOWN)
                self._structure_options[CONF_TEMPORAL_FIELD_ROLES] = time_roles
                self._structure_options[CONF_MEASURE_KINDS] = measure_kinds
                if primary_timestamp:
                    if primary_timestamp not in time_fields:
                        errors[CONF_TIMESTAMP_FIELD] = "invalid_timestamp_field"
                    else:
                        self._structure_options[CONF_TIMESTAMP_FIELD] = primary_timestamp
                elif time_fields:
                    candidates = [
                        field
                        for field, role in time_roles.items()
                        if role in {TIME_ROLE_OBSERVATION, TIME_ROLE_EVENT}
                    ]
                    if len(candidates) == 1:
                        self._structure_options[CONF_TIMESTAMP_FIELD] = candidates[0]
                if not errors:
                    if time_fields:
                        return await self.async_step_temporal()
                    return self.async_create_entry(
                        title="",
                        data={**self._config_entry.options, **self._structure_options},
                    )

        schema: dict[Any, Any] = {}
        if time_fields:
            current_timestamp = self._current(CONF_TIMESTAMP_FIELD)
            schema[
                vol.Optional(
                    CONF_TIMESTAMP_FIELD,
                    default=current_timestamp if current_timestamp in time_fields else "",
                )
            ] = self._one_field_selector(time_fields)
            for role, _label in _TIME_ROLE_OPTIONS:
                schema[
                    vol.Optional(
                        f"{_TIME_ROLE_CATEGORY_PREFIX}{role}",
                        default=[
                            field
                            for field in time_fields
                            if existing_time_roles.get(field) == role
                        ],
                    )
                ] = self._fields_selector(time_fields)
        for kind, _label in _MEASURE_KIND_OPTIONS:
            schema[
                vol.Optional(
                    f"{_MEASURE_KIND_CATEGORY_PREFIX}{kind}",
                    default=[
                        field
                        for field in metric_fields
                        if existing_measure_kinds.get(field) == kind
                    ],
                )
            ] = self._fields_selector(metric_fields)

        if not schema:
            return self.async_create_entry(
                title="",
                data={**self._config_entry.options, **self._structure_options},
            )
        return self.async_show_form(
            step_id="semantics",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_temporal(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow an explicit timestamp-field and timezone override."""
        errors: dict[str, str] = {}
        dataset = self._config_entry.runtime_data.data.dataset
        field_roles = self._structure_options.get(
            CONF_FIELD_ROLES, self._current(CONF_FIELD_ROLES) or {}
        )
        fields = [
            field.name
            for field in dataset.fields
            if field_roles.get(field.name) == FIELD_ROLE_TIME
        ]
        temporal = self._current(CONF_TEMPORAL_PLAN) or {}
        current_plan = temporal.get("plan") or {}
        current_fields = current_plan.get("fields") or {}
        current_timestamp = self._structure_options.get(CONF_TIMESTAMP_FIELD) or current_fields.get(
            "timestamp"
        ) or self._current(CONF_TIMESTAMP_FIELD)
        current_timezone = self._current(CONF_TIMEZONE) or "UTC"
        if user_input is not None:
            submitted = dict(user_input)
            mode = submitted.pop(CONF_TEMPORAL_MODE, _TEMPORAL_AUTO)
            timezone_name = str(submitted.get(CONF_TIMEZONE) or "").strip()
            try:
                ZoneInfo(timezone_name)
            except (ZoneInfoNotFoundError, ValueError):
                errors[CONF_TIMEZONE] = "invalid_timezone"
            else:
                options = {**self._config_entry.options, **self._structure_options}
                if mode == _TEMPORAL_AUTO:
                    options.pop(CONF_TEMPORAL_PLAN, None)
                    options[CONF_TIMEZONE] = timezone_name
                    options[CONF_TIMEZONE_SOURCE] = "user"
                    return self.async_create_entry(title="", data=options)
                timestamp_field = str(submitted.get(CONF_TIMESTAMP_FIELD) or "")
                if timestamp_field not in fields:
                    errors[CONF_TIMESTAMP_FIELD] = "invalid_timestamp_field"
                else:
                    plan = {
                        "status": "resolved",
                        "timezone": {
                            "timezone_name": timezone_name,
                            "source": "user",
                        },
                        "plan": {
                            "strategy": "single_field",
                            "fields": {"timestamp": timestamp_field},
                            "timezone_name": timezone_name,
                            "confidence": 1.0,
                            "parse_success_rate": 1.0,
                            "reasons": ["user-selected timestamp field"],
                        },
                        "warning": None,
                    }
                    options[CONF_TEMPORAL_PLAN] = plan
                    options[CONF_TIMESTAMP_FIELD] = timestamp_field
                    options[CONF_TIMEZONE] = timezone_name
                    options[CONF_TIMEZONE_SOURCE] = "user"
                    return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="temporal",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TEMPORAL_MODE,
                        default=_TEMPORAL_FIELD if current_timestamp else _TEMPORAL_AUTO,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=_TEMPORAL_AUTO,
                                    label="Automatic inference",
                                ),
                                SelectOptionDict(
                                    value=_TEMPORAL_FIELD,
                                    label="Use one timestamp field",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_TIMESTAMP_FIELD,
                        default=current_timestamp if current_timestamp in fields else "",
                    ): self._one_field_selector(fields),
                    vol.Required(CONF_TIMEZONE, default=current_timezone): str,
                }
            ),
            errors=errors,
        )
