"""Config flow for Open Data."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_TIMESTAMP_FIELD,
    DOMAIN,
    PROVIDER_CKAN,
    PROVIDER_SOCRATA,
)
from .providers import create_provider
from .providers.base import OpenDataConnectionError, OpenDataResponseError
from .providers.common import normalize_portal_url


class OpenDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Open Data config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a provider and dataset."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                provider_name = user_input[CONF_PROVIDER]
                portal_url = normalize_portal_url(user_input[CONF_PORTAL_URL])
                dataset_id = user_input[CONF_DATASET_ID].strip()
                resource_id = user_input.get(CONF_RESOURCE_ID, "").strip() or None
                timestamp_field = user_input.get(CONF_TIMESTAMP_FIELD, "").strip() or None
                provider = create_provider(
                    provider_name, async_get_clientsession(self.hass), portal_url
                )
                dataset = await provider.async_get_dataset(dataset_id, resource_id)
            except OpenDataConnectionError:
                errors["base"] = "cannot_connect"
            except (OpenDataResponseError, ValueError):
                errors["base"] = "invalid_dataset"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                unique_id = f"{provider_name}:{portal_url}:{dataset.dataset_id}:{dataset.resource_id or ''}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                data = {
                    CONF_PROVIDER: provider_name,
                    CONF_PORTAL_URL: portal_url,
                    CONF_DATASET_ID: dataset.dataset_id,
                }
                if dataset.resource_id:
                    data[CONF_RESOURCE_ID] = dataset.resource_id
                if timestamp_field:
                    data[CONF_TIMESTAMP_FIELD] = timestamp_field
                return self.async_create_entry(title=dataset.title, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_PROVIDER, default=PROVIDER_CKAN): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=PROVIDER_CKAN, label="CKAN"),
                            SelectOptionDict(value=PROVIDER_SOCRATA, label="Socrata"),
                        ]
                    )
                ),
                vol.Required(CONF_PORTAL_URL): str,
                vol.Required(CONF_DATASET_ID): str,
                vol.Optional(CONF_RESOURCE_ID, default=""): str,
                vol.Optional(CONF_TIMESTAMP_FIELD, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
