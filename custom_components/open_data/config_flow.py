"""Config flow for Open Data."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .analyzer import analyze_dataset, build_selectable_records
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
    CONF_SELECTED_RECORDS,
    CONF_TIMESTAMP_FIELD,
    CONF_TIMESTAMP_FIELDS,
    DOMAIN,
    PROVIDER_CKAN,
    PROVIDER_SOCRATA,
)
from .discovery import DatasetCandidate, rank_datasets, score_dataset
from .field_roles import classify_field_roles
from .models import OpenDataDataset
from .options_flow import OpenDataOptionsFlow
from .portal_inspector import async_discover_catalog, async_inspect_portal
from .preparation import DATA_PREPARATIONS, PreparationRegistry
from .providers import create_provider
from .providers.base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
)
from .reference import (
    OpenDataReference,
    ReferenceConnectionError,
    async_resolve_reference,
    parse_reference,
)

_DISCOVERY_LIMIT = 500
_CATALOG_LIMIT = 500
_AUTO_RECORD_LIMIT = 100
CONF_DATASET_IDS = "dataset_ids"
CONF_SOURCE_LOCATION = "source_location"
CONF_TITLE = "title"


class OpenDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle portal discovery and direct dataset setup."""

    VERSION = 2

    def __init__(self) -> None:
        self._provider_name: str | None = None
        self._portal_url: str | None = None
        self._candidates: dict[str, DatasetCandidate] = {}
        self._preparation_task = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OpenDataOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Resolve one source location into direct setup or portal discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                portal_hint = user_input.get(CONF_PORTAL_URL, "").strip() or None
                reference = parse_reference(
                    user_input[CONF_SOURCE_LOCATION], portal_hint
                )
                reference = await async_resolve_reference(
                    async_get_clientsession(self.hass), reference
                )
                if reference.is_portal:
                    if reference.portal_url is None:
                        raise ValueError("A portal URL could not be determined")
                    return await self._async_begin_portal(reference.portal_url)
                return await self._async_create_from_reference(reference)
            except ReferenceConnectionError:
                errors["base"] = "cannot_connect"
            except OpenDataConnectionError:
                errors["base"] = "cannot_connect"
            except OpenDataSecurityError:
                errors["base"] = "unsafe_source"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_reference"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_LOCATION): str,
                    vol.Optional(CONF_PORTAL_URL, default=""): str,
                }
            ),
            errors=errors,
        )

    async def _async_begin_portal(self, portal_url: str) -> FlowResult:
        """Start or resume bounded catalog preparation for a portal root."""
        registry: PreparationRegistry = self.hass.data[DOMAIN][DATA_PREPARATIONS]
        prepared = registry.get(portal_url)
        if prepared and prepared.status == "ready":
            self._portal_url = prepared.portal_url
            self._provider_name = prepared.provider
            self._set_candidates(prepared.candidates)
            return await self.async_step_discover()

        async def _prepare() -> tuple[str, str, list[DatasetCandidate]]:
            candidates = await self._async_discover_catalog(portal_url)
            if not candidates:
                raise ValueError("no_datasets")
            return (
                self._portal_url or portal_url,
                self._provider_name or "",
                candidates,
            )

        self._portal_url = portal_url
        self._preparation_task = registry.start(portal_url, _prepare)
        return await self.async_step_prepare()

    async def async_step_portal(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Backward-compatible alias for older in-progress flows."""
        if user_input is None:
            return await self.async_step_user()
        source = user_input.get(CONF_PORTAL_URL, "")
        return await self.async_step_user({CONF_SOURCE_LOCATION: source})

    async def async_step_dataset(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Backward-compatible alias for older in-progress flows."""
        return await self.async_step_user(user_input)

    async def _async_create_from_reference(
        self, reference: OpenDataReference
    ) -> FlowResult:
        """Normalize a direct reference into the normal dataset preparation path."""
        if reference.provider not in {PROVIDER_CKAN, PROVIDER_SOCRATA}:
            raise ValueError("Unsupported direct dataset provider")
        if reference.portal_url is None:
            raise ValueError("A portal URL could not be determined")

        provider = create_provider(
            reference.provider,
            async_get_clientsession(self.hass),
            reference.portal_url,
        )
        await provider.async_verify_portal()

        dataset_id = reference.dataset_id
        if (
            reference.provider == PROVIDER_CKAN
            and dataset_id is None
            and reference.resource_id
        ):
            resolver = getattr(provider, "async_resolve_resource_package", None)
            if resolver is None:
                raise ValueError("This CKAN resource cannot be resolved to a dataset")
            dataset_id = await resolver(reference.resource_id)
        if dataset_id is None:
            raise ValueError("A dataset identifier could not be determined")

        self._provider_name = reference.provider
        self._portal_url = reference.portal_url
        entry = await self._async_prepare_dataset_entry(
            OpenDataDataset(
                dataset_id=dataset_id,
                title=dataset_id,
                resource_id=reference.resource_id,
            )
        )
        await self.async_set_unique_id(entry["unique_id"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=entry[CONF_TITLE], data=entry["data"]
        )

    async def async_step_prepare(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Wait for background portal preparation without creating an entry."""
        if self._preparation_task is not None and not self._preparation_task.done():
            return self.async_show_progress(
                step_id="prepare",
                progress_action="prepare_catalog",
                progress_task=self._preparation_task,
            )
        registry: PreparationRegistry = self.hass.data[DOMAIN][DATA_PREPARATIONS]
        prepared = registry.get(self._portal_url or "")
        if prepared and prepared.status == "ready":
            self._portal_url = prepared.portal_url
            self._provider_name = prepared.provider
            self._set_candidates(prepared.candidates)
            return self.async_show_progress_done(next_step_id="discover")
        return self.async_show_progress_done(next_step_id="user")

    def _set_candidates(self, candidates: Any) -> None:
        self._candidates = {
            item.dataset.dataset_id: item
            for item in tuple(candidates)[:_DISCOVERY_LIMIT]
        }

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
        return rank_datasets(datasets)[:_DISCOVERY_LIMIT]

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
