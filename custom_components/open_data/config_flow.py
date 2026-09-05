"""Config flow for Open Data."""

from __future__ import annotations

import asyncio
from functools import partial
import logging
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

from .analysis_api import build_selectable_records
from .analyzer import analyze_dataset
from .const import (
    CONF_DATASET_ID,
    CONF_DATASET_KIND,
    CONF_DISPLAY_FIELD,
    CONF_DISPLAY_FIELDS,
    CONF_FIELD_MAPPINGS,
    CONF_FIELD_ROLES,
    CONF_HIERARCHY_RELATIONSHIPS,
    CONF_IDENTITY_FIELD,
    CONF_IDENTITY_FIELDS,
    CONF_IGNORED_FIELDS,
    CONF_LOCATION_FIELDS,
    CONF_MEASURE_FRESHNESS,
    CONF_MEASURE_KINDS,
    CONF_METRIC_FIELDS,
    CONF_PORTAL_URL,
    CONF_PROFILE_ID,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_SELECTED_FIELDS,
    CONF_SELECTED_RECORDS,
    CONF_TEMPORAL_FIELD_ROLES,
    CONF_TEMPORAL_PLAN,
    CONF_TIMESTAMP_FIELD,
    CONF_TIMESTAMP_FIELDS,
    CONF_TIMEZONE,
    CONF_TIMEZONE_SOURCE,
    DOMAIN,
    PROVIDER_CKAN,
    PROVIDER_SOCRATA,
)
from .data_semantics import (
    TIME_ROLE_EVENT,
    TIME_ROLE_OBSERVATION,
    infer_measure_kind,
    infer_time_roles,
)
from .discovery import DatasetCandidate, rank_datasets, score_dataset
from .field_roles import classify_field_roles
from .flow_diagnostics import log_flow_breadcrumb, log_flow_exception
from .geographic_reference import fips_relationship_hints
from .hierarchy_relationships import (
    infer_relationships,
    merge_relationships,
    relationship_candidate_fields,
)
from .local_discovery import RankedLocalSource, rank_local_sources
from .measure_freshness import build_measure_freshness_profiles, serializable_profiles
from .models import OpenDataDataset
from .options_dyads import OpenDataDyadOptionsFlow
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
from .temporal_policy import resolve_temporal_plan
from .webpage_resolver import ResolvedSourceCandidate, async_resolve_webpage

_DISCOVERY_LIMIT = 500
_CATALOG_LIMIT = 500
_AUTO_RECORD_LIMIT = 100
CONF_DATASET_IDS = "dataset_ids"
CONF_SOURCE_LOCATION = "source_location"
CONF_SOURCE_PROFILE = "source_profile"
CONF_RESOLVED_SOURCE = "resolved_source"
CONF_TITLE = "title"
_INTEGRATION_VERSION = "0.2.0"
_LOGGER = logging.getLogger(__name__)


async def _async_wait_for_background_preparation(task: asyncio.Task[None]) -> None:
    """Let a flow observe preparation without owning or cancelling the work."""
    await asyncio.shield(task)


class OpenDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle local discovery, webpage resolution, and known data sources."""

    VERSION = 3

    def __init__(self) -> None:
        self._provider_name: str | None = None
        self._portal_url: str | None = None
        self._candidates: dict[str, DatasetCandidate] = {}
        self._preparation_task = None
        self._resolved_sources: dict[str, ResolvedSourceCandidate] = {}
        self._local_sources: dict[str, RankedLocalSource] = {}
        self._pending_entries: list[dict[str, Any]] = []

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OpenDataDyadOptionsFlow(config_entry)

    def _diagnostic_context(self, **extra: Any) -> dict[str, Any]:
        return {
            "flow_id": getattr(self, "flow_id", None),
            "portal_url": self._portal_url,
            "provider": self._provider_name,
            "candidate_count": len(self._candidates),
            **extra,
        }

    def _log_unexpected(self, step: str, exc: BaseException, **extra: Any) -> None:
        log_flow_exception(
            step,
            exc,
            integration_version=_INTEGRATION_VERSION,
            **self._diagnostic_context(**extra),
        )

    async def _async_get_preparation_registry(self) -> PreparationRegistry:
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        existing = domain_data.get(DATA_PREPARATIONS)
        if existing is not None:
            return existing
        registry = PreparationRegistry(self.hass)
        await registry.async_load()
        domain_data[DATA_PREPARATIONS] = registry
        return registry

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Start with the user's intent rather than an unexplained URL box."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["local", "website", "known"],
        )

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Suggest source profiles relevant to Home Assistant's configured location."""
        ranked = await self.hass.async_add_executor_job(
            partial(
                rank_local_sources,
                self.hass.config.latitude,
                self.hass.config.longitude,
                importable_only=True,
            )
        )
        self._local_sources = {item.profile.url: item for item in ranked}
        if user_input is not None:
            selected_url = str(user_input.get(CONF_SOURCE_PROFILE) or "")
            selected = self._local_sources.get(selected_url)
            if selected is not None:
                return await self.async_step_known(
                    {CONF_SOURCE_LOCATION: selected.profile.url, CONF_PORTAL_URL: ""}
                )
        options = [
            SelectOptionDict(value=item.profile.url, label=self._local_source_label(item))
            for item in ranked
        ]
        if not options:
            return self.async_abort(reason="no_local_sources")
        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_PROFILE): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=False)
                    )
                }
            ),
        )

    async def async_step_website(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Try to resolve a human-facing page to its upstream public data source."""
        errors: dict[str, str] = {}
        default_url = ""
        if user_input is not None:
            default_url = str(user_input.get(CONF_SOURCE_LOCATION) or "").strip()
            try:
                resolution = await async_resolve_webpage(
                    async_get_clientsession(self.hass), default_url
                )
                self._resolved_sources = {
                    candidate.url: candidate for candidate in resolution.candidates
                }
                log_flow_breadcrumb(
                    "website",
                    "resolved webpage evidence",
                    **self._diagnostic_context(
                        input_url=default_url,
                        page_url=resolution.page_url,
                        page_type=resolution.page_type,
                        resolved_candidate_count=len(self._resolved_sources),
                    ),
                )
                if self._resolved_sources:
                    return await self.async_step_resolved_source()
                errors["base"] = "no_machine_source"
            except OpenDataSecurityError:
                errors["base"] = "unsafe_source"
            except (ReferenceConnectionError, OpenDataConnectionError):
                errors["base"] = "cannot_connect"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_reference"
            except Exception as exc:  # noqa: BLE001
                self._log_unexpected("website", exc, source_location=default_url)
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="website",
            data_schema=vol.Schema(
                {vol.Required(CONF_SOURCE_LOCATION, default=default_url): str}
            ),
            errors=errors,
        )

    async def async_step_resolved_source(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user choose among bounded upstream sources found on a webpage."""
        if user_input is not None:
            selected_url = str(user_input.get(CONF_RESOLVED_SOURCE) or "")
            if selected_url in self._resolved_sources:
                return await self.async_step_known(
                    {CONF_SOURCE_LOCATION: selected_url, CONF_PORTAL_URL: ""}
                )
        options = [
            SelectOptionDict(
                value=candidate.url,
                label=(
                    f"{candidate.kind} · {candidate.relationship} · "
                    f"{candidate.confidence:.0%} confidence · {candidate.url}"
                ),
            )
            for candidate in self._resolved_sources.values()
        ]
        return self.async_show_form(
            step_id="resolved_source",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RESOLVED_SOURCE): SelectSelector(
                        SelectSelectorConfig(options=options, multiple=False)
                    )
                }
            ),
        )

    async def async_step_known(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a portal, dataset page, API URL, resource URL, or dataset ID."""
        errors: dict[str, str] = {}
        source_default = ""
        portal_default = ""
        if user_input is not None:
            source_default = str(user_input.get(CONF_SOURCE_LOCATION) or "").strip()
            portal_default = str(user_input.get(CONF_PORTAL_URL) or "").strip()
            try:
                portal_hint = portal_default or None
                reference = parse_reference(source_default, portal_hint)
                log_flow_breadcrumb(
                    "known",
                    "parsed source reference",
                    **self._diagnostic_context(
                        source_location=source_default,
                        reference_kind=reference.kind,
                        reference_provider=reference.provider,
                        reference_portal_url=reference.portal_url,
                        reference_dataset_id=reference.dataset_id,
                        reference_resource_id=reference.resource_id,
                    ),
                )
                reference = await async_resolve_reference(
                    async_get_clientsession(self.hass), reference
                )
                if reference.is_portal:
                    if reference.portal_url is None:
                        raise ValueError("A portal URL could not be determined")
                    return await self._async_begin_portal(reference.portal_url)
                return await self._async_create_from_reference(reference)
            except (ReferenceConnectionError, OpenDataConnectionError):
                errors["base"] = "cannot_connect"
            except OpenDataSecurityError:
                errors["base"] = "unsafe_source"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_reference"
            except Exception as exc:  # noqa: BLE001
                self._log_unexpected("known", exc, user_input=user_input)
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="known",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_LOCATION, default=source_default): str,
                    vol.Optional(CONF_PORTAL_URL, default=portal_default): str,
                }
            ),
            errors=errors,
        )

    async def _async_begin_portal(self, portal_url: str) -> FlowResult:
        registry = await self._async_get_preparation_registry()
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
            return self._portal_url or portal_url, self._provider_name or "", candidates

        self._portal_url = portal_url
        background_task = registry.start(portal_url, _prepare)
        self._preparation_task = self.hass.async_create_task(
            _async_wait_for_background_preparation(background_task),
            f"Wait for Open Data catalog preparation: {portal_url}",
        )
        return await self.async_step_prepare()

    async def async_step_portal(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is None:
            return await self.async_step_known()
        return await self.async_step_known(
            {CONF_SOURCE_LOCATION: user_input.get(CONF_PORTAL_URL, "")}
        )

    async def async_step_dataset(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_known(user_input)

    async def _async_create_from_reference(self, reference: OpenDataReference) -> FlowResult:
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
        if reference.provider == PROVIDER_CKAN and dataset_id is None and reference.resource_id:
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
        self._pending_entries = [entry]
        return await self.async_step_activate()

    async def async_step_prepare(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._preparation_task is not None and not self._preparation_task.done():
            return self.async_show_progress(
                step_id="prepare",
                progress_action="prepare_catalog",
                progress_task=self._preparation_task,
            )
        registry = await self._async_get_preparation_registry()
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
                self._candidates[item].dataset
                for item in selected_ids
                if item in self._candidates
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
                except Exception as exc:  # noqa: BLE001
                    self._log_unexpected(
                        "discover", exc, selected_dataset_ids=selected_ids
                    )
                    errors["base"] = "unknown"
                else:
                    self._pending_entries = entries
                    return await self.async_step_activate()
        options = [
            SelectOptionDict(
                value=c.dataset.dataset_id,
                label=self._candidate_label(c),
            )
            for c in self._candidates.values()
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

    async def async_step_activate(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Explicitly cross from prepared datasets into active HA config entries."""
        if not self._pending_entries:
            return self.async_abort(reason="no_pending_datasets")
        first = self._pending_entries[0]
        if user_input is not None:
            for extra in self._pending_entries[1:]:
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
        titles = ", ".join(entry[CONF_TITLE] for entry in self._pending_entries[:5])
        if len(self._pending_entries) > 5:
            titles = f"{titles}, +{len(self._pending_entries) - 5} more"
        return self.async_show_form(
            step_id="activate",
            data_schema=vol.Schema({}),
            description_placeholders={
                "count": str(len(self._pending_entries)),
                "datasets": titles,
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
        datasets, _errors = await async_discover_catalog(
            inspected, limit=_CATALOG_LIMIT
        )
        ranked = await self.hass.async_add_executor_job(rank_datasets, datasets)
        return ranked[:_DISCOVERY_LIMIT]

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
            dataset.dataset_id, dataset.resource_id, limit=80
        )
        structure = await self.hass.async_add_executor_job(
            analyze_dataset, dataset, sample_rows
        )
        candidate = score_dataset(dataset)
        temporal = resolve_temporal_plan(
            tuple(field.name for field in dataset.fields),
            sample_rows,
            home_assistant_timezone=self.hass.config.time_zone,
        )
        freshness = build_measure_freshness_profiles(
            sample_rows,
            metric_fields=structure.metric_fields,
            timestamp_fields=structure.timestamp_fields,
            timezone_name=temporal.timezone.timezone_name,
        )
        selected_fields = [
            field
            for field in structure.metric_fields
            if freshness.get(field) is None or freshness[field].auto_import
        ]
        labels = {field.name: field.label for field in dataset.fields}
        temporal_roles = infer_time_roles(
            (field, labels.get(field)) for field in structure.timestamp_fields
        )
        measure_kinds = {
            field: infer_measure_kind(field, labels.get(field))
            for field in structure.metric_fields
        }
        structural_fields = relationship_candidate_fields(
            sample_rows,
            identity_fields=structure.identity_fields,
            location_fields=structure.location_fields,
            hierarchy_fields=structure.hierarchy_fields,
        )
        inferred_relationships = infer_relationships(sample_rows, structural_fields)
        reference_relationships = await self.hass.async_add_executor_job(
            fips_relationship_hints,
            sample_rows,
            tuple(field.name for field in dataset.fields),
        )
        hierarchy_relationships = merge_relationships(
            inferred_relationships,
            reference_relationships,
        )
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
            CONF_SELECTED_FIELDS: selected_fields,
            CONF_MEASURE_KINDS: measure_kinds,
            CONF_IDENTITY_FIELDS: list(structure.identity_fields),
            CONF_DISPLAY_FIELDS: list(structure.display_fields),
            CONF_TIMESTAMP_FIELDS: list(structure.timestamp_fields),
            CONF_TEMPORAL_FIELD_ROLES: temporal_roles,
            CONF_LOCATION_FIELDS: list(structure.location_fields),
            CONF_FIELD_ROLES: classify_field_roles(
                dataset,
                structure,
                sample_rows=sample_rows,
            ),
            CONF_HIERARCHY_RELATIONSHIPS: [
                item.as_dict() for item in hierarchy_relationships
            ],
            CONF_SELECTED_RECORDS: build_selectable_records(
                dataset,
                sample_rows,
                structure.identity_fields,
                structure.display_fields,
                limit=_AUTO_RECORD_LIMIT,
            ),
            CONF_PROFILE_ID: candidate.profile_id,
            CONF_FIELD_MAPPINGS: candidate.field_mappings,
            CONF_TEMPORAL_PLAN: temporal.as_dict(),
            CONF_TIMEZONE: temporal.timezone.timezone_name,
            CONF_TIMEZONE_SOURCE: temporal.timezone.source,
            CONF_MEASURE_FRESHNESS: serializable_profiles(freshness),
        }
        if dataset.resource_id:
            data[CONF_RESOURCE_ID] = dataset.resource_id
        if structure.identity_fields:
            data[CONF_IDENTITY_FIELD] = structure.identity_fields[0]
        if structure.display_fields:
            data[CONF_DISPLAY_FIELD] = structure.display_fields[0]

        temporal_dict = temporal.as_dict()
        resolved_timestamp = (
            ((temporal_dict.get("plan") or {}).get("fields") or {}).get("timestamp")
        )
        if resolved_timestamp in structure.timestamp_fields:
            data[CONF_TIMESTAMP_FIELD] = resolved_timestamp
        elif len(structure.timestamp_fields) == 1:
            data[CONF_TIMESTAMP_FIELD] = structure.timestamp_fields[0]
        else:
            semantic_candidates = [
                field
                for field, role in temporal_roles.items()
                if role in {TIME_ROLE_OBSERVATION, TIME_ROLE_EVENT}
            ]
            if len(semantic_candidates) == 1:
                data[CONF_TIMESTAMP_FIELD] = semantic_candidates[0]
        return {"unique_id": unique_id, CONF_TITLE: dataset.title, "data": data}

    @staticmethod
    def _candidate_label(candidate: DatasetCandidate) -> str:
        title = candidate.dataset.title or candidate.dataset.dataset_id
        suffixes: list[str] = []
        profile_id = getattr(candidate, "profile_id", None)
        if profile_id:
            suffixes.append(str(profile_id))
        freshness_label = getattr(candidate, "freshness_label", None)
        if freshness_label:
            suffixes.append(str(freshness_label))
        return " · ".join((title, *suffixes))

    @staticmethod
    def _local_source_label(item: RankedLocalSource) -> str:
        profile = item.profile
        relevance = "applies here" if item.applies_here else "useful nearby"
        distance = (
            f" · {item.distance_km:.0f} km"
            if item.distance_km is not None and not item.applies_here
            else ""
        )
        topics = ", ".join(profile.topics[:4])
        return (
            f"{profile.name} · {relevance}{distance} · "
            f"{profile.validation_label} · {topics}"
        )
