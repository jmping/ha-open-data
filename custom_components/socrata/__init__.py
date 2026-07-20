"""Socrata Open Data integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SocrataClient
from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_TIMESTAMP_FIELD,
    DEFAULT_TIMESTAMP_FIELD,
    PLATFORMS,
)
from .coordinator import SocrataDataUpdateCoordinator


type SocrataConfigEntry = ConfigEntry[SocrataDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SocrataConfigEntry) -> bool:
    """Set up Socrata from a config entry."""
    client = SocrataClient(
        async_get_clientsession(hass), entry.data[CONF_PORTAL_URL]
    )
    coordinator = SocrataDataUpdateCoordinator(
        hass,
        client,
        entry.data[CONF_DATASET_ID],
        entry.data.get(CONF_TIMESTAMP_FIELD, DEFAULT_TIMESTAMP_FIELD),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SocrataConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
