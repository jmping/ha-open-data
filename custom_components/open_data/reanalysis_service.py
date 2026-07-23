"""Manual service surface for bounded dataset re-analysis."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .reanalysis_runtime import DATA_REANALYSIS_CONTROLLERS

SERVICE_REANALYZE_ENTRY = "reanalyze_entry"
CONF_ENTRY_ID = "entry_id"


async def async_register_reanalysis_service(hass: HomeAssistant) -> None:
    """Register explicit manual re-analysis."""

    async def async_reanalyze_entry(call: ServiceCall):
        entry_id = call.data[CONF_ENTRY_ID]
        controller = hass.data.get(DOMAIN, {}).get(
            DATA_REANALYSIS_CONTROLLERS, {}
        ).get(entry_id)
        if controller is None:
            raise ValueError("Loaded Open Data config entry was not found")
        return await controller.async_run(manual=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REANALYZE_ENTRY,
        async_reanalyze_entry,
        schema=vol.Schema({vol.Required(CONF_ENTRY_ID): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
