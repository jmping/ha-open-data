"""Config and options flows for Open Data."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_SELECTED_FIELDS,
    DOMAIN,
)
from .discovery import DatasetCandidate, rank_datasets
from .models import OpenDataDataset
from .providers import async_detect_provider, create_provider
from .providers.base import (
    OpenDataConnectionError,
    OpenDataResponseError,
    OpenDataSecurityError,
)
from .providers.common import normalize_portal_url

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
    """Handle an Open Data config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._provider_name: str | None = None
        self._portal_url: str | None = None
        self._candidates: dict[str, DatasetCandidate] = {}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return OpenDataOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Scan a portal, auto-detect its provider, and discover datasets."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._portal_url = normalize_portal_url(user_input[CONF_PORTAL_URL])
                datasets = await self._async_discover_catalog()
            except OpenDataSecurityError:
                errors["base"] = "invalid_dataset"
            except OpenDataConnectionError:
                errors["base"] = "cannot_connect"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_dataset"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                ranked = rank_datasets(datasets)
                self._candidates = {
                    item.dataset.dataset_id: item for item in ranked[:_DISCOVERY_LIMIT]
                }
                if self._candidates:
                    return await self.async_step_discover()
                errors["base"] = "no_datasets"

        schema = vol.Schema({vol.Required(CONF_PORTAL_URL): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select one of the automatically discovered datasets."""
        errors: dict[str, str] = {}
        if user_input is not None:
            dataset_id = user_input[CONF_DATASET_ID]
            candidate = self._candidates.get(dataset_id)
            if candidate is None:
                errors["base"] = "invalid_dataset"
            else:
                try:
                    return await self._async_create_dataset_entry(candidate.dataset)
                except OpenDataConnectionError:
                    errors["base"] = "cannot_connect"
                except (OpenDataResponseError, OpenDataSecurityError, ValueError):
                    errors["base"] = "invalid_dataset"
                except Exception:  # noqa: BLE001
                    errors["base"] = "unknown"

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
                    vol.Required(CONF_DATASET_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
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

    async def _async_discover_catalog(self) -> list[OpenDataDataset]:
        """Detect the provider and search broad catalog slices."""
        if self._portal_url is None:
            raise ValueError("Discovery flow is missing portal state")
        self._provider_name, provider = await async_detect_provider(
            async_get_clientsession(self.hass), self._portal_url
        )
        found: dict[str, OpenDataDataset] = {}
        last_error: OpenDataResponseError | None = None
        for query in _DISCOVERY_QUERIES:
            try:
                datasets = await provider.async_search_datasets(
                    query, limit=_DISCOVERY_LIMIT
                )
            except OpenDataResponseError as err:
                last_error = err
                continue
            for dataset in datasets:
                found.setdefault(dataset.dataset_id, dataset)
        if not found and last_error is not None:
            raise last_error
        return list(found.values())

    async def _async_create_dataset_entry(
        self, discovered: OpenDataDataset
    ) -> FlowResult:
        """Inspect the selected schema and create the config entry."""
        if self._provider_name is None or self._portal_url is None:
            raise ValueError("Discovery flow is missing provider state")
        provider = create_provider(
            self._provider_name,
            async_get_clientsession(self.hass),
            self._portal_url,
        )
        await provider.async_verify_portal()
        dataset = await provider.async_get_dataset(discovered.dataset_id)
        unique_id = (
            f"{self._provider_name}:{self._portal_url}:"
            f"{dataset.dataset_id}:{dataset.resource_id or ''}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        data = {
            CONF_PROVIDER: self._provider_name,
            CONF_PORTAL_URL: self._portal_url,
            CONF_DATASET_ID: dataset.dataset_id,
        }
        if dataset.resource_id:
            data[CONF_RESOURCE_ID] = dataset.resource_id
        return self.async_create_entry(title=dataset.title, data=data)

    @staticmethod
    def _candidate_label(candidate: DatasetCandidate) -> str:
        """Build a compact, explainable selector label."""
        reasons = ", ".join(candidate.reasons[:3])
        suffix = f" — {reasons}" if reasons else ""
        title = candidate.dataset.title[:100]
        return f"{candidate.score:03d} · {title}{suffix}"[:150]


class OpenDataOptionsFlow(config_entries.OptionsFlow):
    """Choose which discovered fields become entities."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage field selection."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        coordinator = self._config_entry.runtime_data
        choices = {
            field.name: field.label for field in coordinator.data.dataset.fields
        }
        current = list(
            self._config_entry.options.get(CONF_SELECTED_FIELDS, choices.keys())
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SELECTED_FIELDS, default=current
                    ): cv.multi_select(choices)
                }
            ),
        )
