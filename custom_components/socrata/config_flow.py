"""Config flow for Socrata Open Data."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SocrataClient, SocrataConnectionError, SocrataResponseError
from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_TIMESTAMP_FIELD,
    DEFAULT_TIMESTAMP_FIELD,
    DOMAIN,
)


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> str:
    """Validate config-flow input and return a display title."""
    client = SocrataClient(async_get_clientsession(hass), data[CONF_PORTAL_URL])
    metadata = await client.async_get_dataset_metadata(data[CONF_DATASET_ID])
    await client.async_latest_row(
        data[CONF_DATASET_ID],
        data.get(CONF_TIMESTAMP_FIELD, DEFAULT_TIMESTAMP_FIELD),
    )
    return metadata.name


class SocrataConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Socrata."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial user configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            unique_id = (
                f"{user_input[CONF_PORTAL_URL].rstrip('/').lower()}::"
                f"{user_input[CONF_DATASET_ID].lower()}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                title = await _async_validate_input(self.hass, user_input)
            except SocrataConnectionError:
                errors["base"] = "cannot_connect"
            except SocrataResponseError:
                errors["base"] = "invalid_response"
            except (ValueError, KeyError):
                errors["base"] = "invalid_input"
            else:
                return self.async_create_entry(title=title, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_PORTAL_URL): str,
                vol.Required(CONF_DATASET_ID): str,
                vol.Optional(
                    CONF_TIMESTAMP_FIELD, default=DEFAULT_TIMESTAMP_FIELD
                ): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )
