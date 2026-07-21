"""Config and options flows for Open Data."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .analyzer import DatasetStructure, analyze_dataset, build_selectable_records
from .const import (
    CONF_DATASET_ID,
    CONF_DATASET_KIND,
    CONF_DISPLAY_FIELD,
    CONF_DISPLAY_FIELDS,
    CONF_FIELD_MAPPINGS,
    CONF_FIELD_ROLES,
    CONF_HIERARCHY_FIELDS,
    CONF_IDENTITY_FIELD,
    CONF_IDENTITY_FIELDS,
    CONF_IGNORED_FIELDS,
    CONF_LOCATION_FIELDS,
    CONF_METRIC_FIELDS,
    CONF_PORTAL_URL,
    CONF_PROFILE_ID,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_RECORD_KEY_FIELDS,
    CONF_RECORD_LABEL_FIELDS,
    CONF_RECORD_STRUCTURE,
    CONF_SELECTED_FIELDS,
    CONF_SELECTED_RECORDS,
    CONF_TIMESTAMP_FIELD,
    CONF_TIMESTAMP_FIELDS,
    CONF_UNIT_KEY_FIELDS,
    CONF_UNIT_LABEL_FIELDS,
    DOMAIN,
)
from .discovery import DatasetCandidate, rank_datasets, score_dataset
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
from .models import OpenDataDataset
from .portal_inspector import async_discover_catalog, async_inspect_portal
from .providers import create_provider
from .providers.base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
)
from .record_structure import build_record_structure

_DISCOVERY_LIMIT = 50
_CATALOG_LIMIT = 500
_VALIDATION_LIMIT = 150
_RECORD_LIMIT = 500
_AUTO_RECORD_LIMIT = 100
_FIELD_ROLE_CATEGORY_PREFIX = "field_role_fields__"
_FIELD_ROLE_OPTIONS = (
    (FIELD_ROLE_LOCATION, "Location"),
    (FIELD_ROLE_TIME, "Time"),
    (FIELD_ROLE_DATA, "Data / measurement"),
    (FIELD_ROLE_MEASUREMENT_NAME, "Measurement name (long format)"),
    (FIELD_ROLE_DESCRIPTIVE, "Descriptive"),
    (FIELD_ROLE_IRRELEVANT, "Irrelevant"),
)
CONF_DATASET_IDS = "dataset_ids"
CONF_TITLE = "title"


class OpenDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Open Data config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._provider_name: str | None = None
        self._portal_url: str | None = None
        self._candidates: dict[str, DatasetCandidate] = {}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OpenDataOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                candidates = await self._async_discover_catalog(user_input[CONF_PORTAL_URL])
            except OpenDataSecurityError:
                errors["base"] = "invalid_dataset"
            except OpenDataConnectionError:
                errors["base"] = "cannot_connect"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_dataset"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                self._candidates = {
                    item.dataset.dataset_id: item
                    for item in candidates[:_DISCOVERY_LIMIT]
                }
                if self._candidates:
                    return await self.async_step_discover()
                errors["base"] = "no_datasets"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PORTAL_URL): str}),
            errors=errors,
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_ids = user_input[CONF_DATASET_IDS]
            if isinstance(selected_ids, str):
                selected_ids = [selected_ids]
            selected = [
                self._candidates[dataset_id].dataset
                for dataset_id in selected_ids
                if dataset_id in self._candidates
            ]
            if not selected or len(selected) != len(selected_ids):
                errors["base"] = "invalid_dataset"
            else:
                try:
                    entries = [
                        await self._async_prepare_dataset_entry(dataset)
                        for dataset in selected
                    ]
                except OpenDataConnectionError:
                    errors["base"] = "cannot_connect"
                except (OpenDataResponseError, OpenDataSecurityError, ValueError):
                    errors["base"] = "invalid_dataset"
                except Exception:  # noqa: BLE001
                    errors["base"] = "unknown"
                else:
                    first = entries[0]
                    for extra in entries[1:]:
                        self.hass.async_create_task(
                            self.hass.config_entries.flow.async_init(
                                DOMAIN,
                                context={"source": config_entries.SOURCE_IMPORT},
                                data=extra,
                            )
                        )
                    await self.async_set_unique_id(first["unique_id"])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=first[CONF_TITLE], data=first["data"]
                    )

        options = [
            SelectOptionDict(
                value=candidate.dataset.dataset_id,
                label=self._candidate_label(candidate),
            )
            for candidate in self._candidates.values()
        ]
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DATASET_IDS): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "portal": self._portal_url or "",
                "count": str(len(options)),
                "provider": self._provider_name or "",
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        await self.async_set_unique_id(import_data["unique_id"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=import_data[CONF_TITLE], data=import_data["data"]
        )

    async def _async_discover_catalog(self, portal_url: str) -> list[DatasetCandidate]:
        inspected = await async_inspect_portal(
            async_get_clientsession(self.hass), portal_url
        )
        self._portal_url = inspected.description.portal_url
        self._provider_name = inspected.description.provider
        datasets, _errors = await async_discover_catalog(inspected, limit=_CATALOG_LIMIT)
        ranked = rank_datasets(datasets)
        usable: list[DatasetCandidate] = []
        for candidate in ranked[:_VALIDATION_LIMIT]:
            try:
                dataset = await inspected.provider.async_get_dataset(
                    candidate.dataset.dataset_id
                )
            except OpenDataResponseError:
                continue
            usable.append(score_dataset(dataset))
            if len(usable) >= _DISCOVERY_LIMIT:
                break
        return sorted(
            usable, key=lambda item: (-item.score, item.dataset.title.casefold())
        )

    async def _async_prepare_dataset_entry(
        self, discovered: OpenDataDataset
    ) -> dict[str, Any]:
        if self._provider_name is None or self._portal_url is None:
            raise ValueError("Discovery flow is missing provider state")
        provider = create_provider(
            self._provider_name,
            async_get_clientsession(self.hass),
            self._portal_url,
        )
        await provider.async_verify_portal()
        dataset = await provider.async_get_dataset(
            discovered.dataset_id, discovered.resource_id
        )
        sample_rows = await provider.async_sample_rows(
            dataset.dataset_id, dataset.resource_id, limit=50
        )
        structure = analyze_dataset(dataset, sample_rows)
        candidate = score_dataset(dataset)
        unique_id = (
            f"{self._provider_name}:{self._portal_url}:"
            f"{dataset.dataset_id}:{dataset.resource_id or ''}"
        )
        data: dict[str, Any] = {
            CONF_PROVIDER: self._provider_name,
            CONF_PORTAL_URL: self._portal_url,
            CONF_DATASET_ID: dataset.dataset_id,
            CONF_DATASET_KIND: structure.kind,
            CONF_IGNORED_FIELDS: list(structure.ignored_fields),
            CONF_METRIC_FIELDS: list(structure.metric_fields),
            CONF_IDENTITY_FIELDS: list(structure.identity_fields),
            CONF_DISPLAY_FIELDS: list(structure.display_fields),
            CONF_TIMESTAMP_FIELDS: list(structure.timestamp_fields),
            CONF_LOCATION_FIELDS: list(structure.location_fields),
            CONF_HIERARCHY_FIELDS: list(structure.hierarchy_fields),
        }
        structural_fields = {
            structure.identity_field,
            structure.display_field,
            *structure.location_fields,
        }
        structural_fields.discard(None)
        data[CONF_FIELD_ROLES] = classify_field_roles(
            (field.name for field in dataset.fields),
            sample_rows,
            configured_metrics=structure.metric_fields,
            structural_fields=structural_fields,
            timestamp_fields=structure.timestamp_fields,
            ignored_fields=structure.ignored_fields,
        ).as_assignments()
        if dataset.resource_id:
            data[CONF_RESOURCE_ID] = dataset.resource_id
        if structure.identity_field:
            data[CONF_IDENTITY_FIELD] = structure.identity_field
        if structure.display_field:
            data[CONF_DISPLAY_FIELD] = structure.display_field
        if structure.timestamp_field:
            data[CONF_TIMESTAMP_FIELD] = structure.timestamp_field
        if candidate.profile_id:
            data[CONF_PROFILE_ID] = candidate.profile_id
            data[CONF_FIELD_MAPPINGS] = [
                {
                    "source_field": mapping.source_field,
                    "canonical_metric": mapping.canonical_metric,
                    "mapping_method": mapping.mapping_method,
                    "confidence": mapping.confidence,
                }
                for mapping in candidate.field_mappings
            ]

        if structure.identity_field:
            rows = await provider.async_distinct_rows(
                dataset.dataset_id,
                dataset.resource_id,
                structure.identity_field,
                structure.display_field,
                structure.hierarchy_fields,
                limit=_AUTO_RECORD_LIMIT,
            )
            records = build_selectable_records(rows, structure)
            data[CONF_SELECTED_RECORDS] = [record.value for record in records]

        return {"unique_id": unique_id, CONF_TITLE: dataset.title, "data": data}

    @staticmethod
    def _candidate_label(candidate: DatasetCandidate) -> str:
        reasons = ", ".join(candidate.reasons[:3])
        suffix = f" — {reasons}" if reasons else ""
        title = candidate.dataset.title[:100]
        return f"{candidate.score:03d} · {title}{suffix}"[:150]


class OpenDataOptionsFlow(config_entries.OptionsFlow):
    """Choose structural fields first, then records/locations and metrics."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._structure_options: dict[str, Any] = {}

    @staticmethod
    def _field_selector(values: list[str]) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=value, label=value) for value in values],
                multiple=False,
            )
        )

    @staticmethod
    def _fields_selector(values: list[str]) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=value, label=value) for value in values
                ],
                multiple=True,
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
        identity_fields = list(
            dict.fromkeys(
                (*self._config_entry.data.get(CONF_IDENTITY_FIELDS, ()), *all_fields)
            )
        )
        display_fields = list(
            dict.fromkeys(
                (*self._config_entry.data.get(CONF_DISPLAY_FIELDS, ()), *all_fields)
            )
        )
        timestamp_fields = list(
            dict.fromkeys(
                (*self._config_entry.data.get(CONF_TIMESTAMP_FIELDS, ()), *all_fields)
            )
        )
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
                *self._config_entry.data.get(CONF_LOCATION_FIELDS, ()),
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
        display = self._current(CONF_DISPLAY_FIELD)
        timestamp = self._current(CONF_TIMESTAMP_FIELD)
        if identity_fields:
            schema[vol.Optional(CONF_IDENTITY_FIELD, default=identity)] = self._field_selector(
                identity_fields
            )
        if display_fields:
            schema[vol.Optional(CONF_DISPLAY_FIELD, default=display)] = self._field_selector(
                display_fields
            )
        if timestamp_fields:
            schema[vol.Optional(CONF_TIMESTAMP_FIELD, default=timestamp)] = self._field_selector(
                timestamp_fields
            )
        role_fields = [field.name for field in dataset.fields]
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
            submitted[CONF_RECORD_STRUCTURE] = build_record_structure(
                unit_key_fields=submitted.get(CONF_UNIT_KEY_FIELDS, ()),
                unit_label_fields=submitted.get(CONF_UNIT_LABEL_FIELDS, ()),
                record_key_fields=submitted.get(CONF_RECORD_KEY_FIELDS, ()),
                record_label_fields=submitted.get(CONF_RECORD_LABEL_FIELDS, ()),
                parent_levels=tuple(
                    {
                        "name": f"parent_{index}",
                        "key_fields": (field,),
                        "label_fields": (field,),
                    }
                    for index, field in enumerate(
                        submitted.get(CONF_HIERARCHY_FIELDS, ()), start=1
                    )
                ),
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
        schema: dict[Any, Any] = {
            vol.Optional(
                CONF_HIERARCHY_FIELDS,
                default=[
                    field
                    for field in (self._current(CONF_HIERARCHY_FIELDS) or ())
                    if field in label_fields
                ],
            ): self._fields_selector(label_fields),
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
        default_fields = metrics & choices.keys()
        current_fields = list(
            self._config_entry.options.get(CONF_SELECTED_FIELDS, default_fields)
        )
        schema: dict[Any, Any] = {
            vol.Optional(CONF_SELECTED_FIELDS, default=current_fields): cv.multi_select(
                choices
            )
        }

        identity = self._structure_options.get(CONF_IDENTITY_FIELD)
        display = self._structure_options.get(CONF_DISPLAY_FIELD)
        timestamp = self._structure_options.get(CONF_TIMESTAMP_FIELD)
        hierarchy_fields = tuple(
            self._structure_options.get(
                CONF_HIERARCHY_FIELDS,
                self._config_entry.data.get(CONF_HIERARCHY_FIELDS, ()),
            )
        )
        if identity:
            rows = await coordinator.provider.async_distinct_rows(
                dataset.dataset_id,
                dataset.resource_id,
                identity,
                display,
                hierarchy_fields,
                limit=_RECORD_LIMIT,
            )
            structure = DatasetStructure(
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
            records = build_selectable_records(rows, structure)
            record_choices = {record.value: record.label for record in records}
            if record_choices:
                configured = self._config_entry.options.get(
                    CONF_SELECTED_RECORDS,
                    self._config_entry.data.get(CONF_SELECTED_RECORDS, ()),
                )
                configured_values = (
                    [configured] if isinstance(configured, str) else list(configured or ())
                )
                current_records = [
                    value for value in configured_values if value in record_choices
                ]
                if not current_records:
                    current_records = list(record_choices)
                schema[
                    vol.Optional(CONF_SELECTED_RECORDS, default=current_records)
                ] = cv.multi_select(record_choices)

        return self.async_show_form(
            step_id="records",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "kind": self._config_entry.data.get(CONF_DATASET_KIND, "table"),
                "identity": identity or "none",
            },
        )
