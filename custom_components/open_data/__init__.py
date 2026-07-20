"""Open Data integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_TIMESTAMP_FIELD,
    PLATFORMS,
)
from .coordinator import OpenDataCoordinator
from .providers import create_provider


type OpenDataConfigEntry = ConfigEntry[OpenDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Set up Open Data from a config entry."""
    provider = create_provider(
        entry.data[CONF_PROVIDER],
        async_get_clientsession(hass),
        entry.data[CONF_PORTAL_URL],
    )
    coordinator = OpenDataCoordinator(
        hass,
        provider,
        entry.data[CONF_DATASET_ID],
        entry.data.get(CONF_RESOURCE_ID),
        entry.data.get(CONF_TIMESTAMP_FIELD) or None,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
