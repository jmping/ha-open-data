"""Config and options flows for Open Data."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .const import (
    CONF_DATASET_ID,
    CONF_ENTRY_TYPE,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_SELECTED_FIELDS,
    CONF_SOURCE_LOCATION,
    DOMAIN,
    ENTRY_TYPE_DATASET,
    ENTRY_TYPE_PORTAL,
)
from .discovery import DatasetCandidate, rank_datasets
from .models import OpenDataDataset
from .providers import create_provider
from .providers.base import OpenDataConnectionError, OpenDataResponseError
from .reference import OpenDataReference, async_resolve_reference, parse_reference

_DISCOVERY_QUERIES = (
    "",
    "environment",
    "air quality",
    "weather",
    "rainfall",
    "water",
    "temperature",
    "climate",
    "energy",
)
_DISCOVERY_LIMIT = 50


class OpenDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a portal index or one independently updating dataset."""

    VERSION = 2
    MINOR_VERSION = 0

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow for this entry type."""
        if config_entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DATASET) == ENTRY_TYPE_PORTAL:
            return OpenDataPortalOptionsFlow(config_entry)
        return OpenDataDatasetOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choose whether to index a portal or add a dataset directly."""
        return self.async_show_menu(step_id="user", menu_options=["portal", "dataset"])

    async def async_step_portal(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Create a portal index, or create a dataset launched from one."""
        if user_input and CONF_DATASET_ID in user_input and CONF_PROVIDER in user_input:
            reference = OpenDataReference(
                provider=user_input[CONF_PROVIDER],
                portal_url=user_input[CONF_PORTAL_URL],
                dataset_id=user_input[CONF_DATASET_ID],
                resource_id=user_input.get(CONF_RESOURCE_ID),
            )
            return await self._async_create_dataset(reference)

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                reference = parse_reference(user_input[CONF_SOURCE_LOCATION])
                reference = await async_resolve_reference(
                    async_get_clientsession(self.hass), reference
                )
                if not reference.is_portal or reference.portal_url is None or reference.provider is None:
                    raise ValueError("Location is not a portal root")
                provider = create_provider(
                    reference.provider,
                    async_get_clientsession(self.hass),
                    reference.portal_url,
                )
                await provider.async_search_datasets("", limit=1)
            except OpenDataConnectionError:
                errors["base"] = "cannot_connect"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_portal"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                unique_id = f"portal:{reference.provider}:{reference.portal_url}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=reference.portal_url.removeprefix("https://").removeprefix("http://"),
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_PORTAL,
                        CONF_PROVIDER: reference.provider,
                        CONF_PORTAL_URL: reference.portal_url,
                        CONF_SOURCE_LOCATION: user_input[CONF_SOURCE_LOCATION].strip(),
                    },
                )

        return self.async_show_form(
            step_id="portal",
            data_schema=vol.Schema({vol.Required(CONF_SOURCE_LOCATION): str}),
            errors=errors,
        )

    async def async_step_dataset(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Add one dataset from a URL, API endpoint, or provider ID."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                portal_hint = user_input.get(CONF_PORTAL_URL, "").strip() or None
                reference = parse_reference(user_input[CONF_SOURCE_LOCATION], portal_hint)
                reference = await async_resolve_reference(
                    async_get_clientsession(self.hass), reference
                )
                if reference.dataset_id is None:
                    raise ValueError("A dataset identifier could not be determined")
                return await self._async_create_dataset(
                    reference,
                    source_location=user_input[CONF_SOURCE_LOCATION].strip(),
                )
            except OpenDataConnectionError:
                errors["base"] = "cannot_connect"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_dataset"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="dataset",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOURCE_LOCATION): str,
                    vol.Optional(CONF_PORTAL_URL, default=""): str,
                }
            ),
            errors=errors,
        )

    async def _async_create_dataset(
        self,
        reference: OpenDataReference,
        source_location: str | None = None,
    ) -> FlowResult:
        """Validate and create one independently updating dataset entry."""
        if reference.provider is None or reference.portal_url is None or reference.dataset_id is None:
            raise ValueError("Dataset reference is incomplete")
        provider = create_provider(
            reference.provider,
            async_get_clientsession(self.hass),
            reference.portal_url,
        )
        dataset = await provider.async_get_dataset(reference.dataset_id, reference.resource_id)
        unique_id = (
            f"dataset:{reference.provider}:{reference.portal_url}:"
            f"{dataset.dataset_id}:{dataset.resource_id or ''}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        data = {
            CONF_ENTRY_TYPE: ENTRY_TYPE_DATASET,
            CONF_PROVIDER: reference.provider,
            CONF_PORTAL_URL: reference.portal_url,
            CONF_DATASET_ID: dataset.dataset_id,
        }
        if dataset.resource_id:
            data[CONF_RESOURCE_ID] = dataset.resource_id
        if source_location:
            data[CONF_SOURCE_LOCATION] = source_location
        return self.async_create_entry(title=dataset.title, data=data)


class OpenDataPortalOptionsFlow(config_entries.OptionsFlow):
    """Search a portal and launch separate dataset config flows."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._candidates: dict[str, DatasetCandidate] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Discover and rank datasets exposed by this portal."""
        if not self._candidates:
            datasets = await self._async_discover_catalog()
            self._candidates = {
                candidate.dataset.dataset_id: candidate
                for candidate in rank_datasets(datasets)[:_DISCOVERY_LIMIT]
            }
        if user_input is not None:
            candidate = self._candidates[user_input[CONF_DATASET_ID]]
            await self.hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "portal"},
                data={
                    CONF_PROVIDER: self._config_entry.data[CONF_PROVIDER],
                    CONF_PORTAL_URL: self._config_entry.data[CONF_PORTAL_URL],
                    CONF_DATASET_ID: candidate.dataset.dataset_id,
                    **(
                        {CONF_RESOURCE_ID: candidate.dataset.resource_id}
                        if candidate.dataset.resource_id
                        else {}
                    ),
                },
            )
            return self.async_create_entry(title="", data={})

        options = [
            SelectOptionDict(
                value=candidate.dataset.dataset_id,
                label=self._candidate_label(candidate),
            )
            for candidate in self._candidates.values()
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DATASET_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
            description_placeholders={"count": str(len(options))},
        )

    async def _async_discover_catalog(self) -> list[OpenDataDataset]:
        provider = create_provider(
            self._config_entry.data[CONF_PROVIDER],
            async_get_clientsession(self.hass),
            self._config_entry.data[CONF_PORTAL_URL],
        )
        found: dict[str, OpenDataDataset] = {}
        for query in _DISCOVERY_QUERIES:
            for dataset in await provider.async_search_datasets(query, limit=_DISCOVERY_LIMIT):
                found.setdefault(dataset.dataset_id, dataset)
        return list(found.values())

    @staticmethod
    def _candidate_label(candidate: DatasetCandidate) -> str:
        reasons = ", ".join(candidate.reasons[:3])
        suffix = f" — {reasons}" if reasons else ""
        return f"{candidate.score:03d} · {candidate.dataset.title}{suffix}"


class OpenDataDatasetOptionsFlow(config_entries.OptionsFlow):
    """Choose which discovered fields become entities."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage field selection."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        coordinator = self._config_entry.runtime_data
        choices = {field.name: field.label for field in coordinator.data.dataset.fields}
        current = list(self._config_entry.options.get(CONF_SELECTED_FIELDS, choices.keys()))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SELECTED_FIELDS, default=current): cv.multi_select(choices)
                }
            ),
        )
