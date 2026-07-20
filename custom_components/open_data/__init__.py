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
    DOMAIN,
    PLATFORMS,
)
from .coordinator import OpenDataCoordinator
from .feedback import FeedbackRegistry
from .providers import create_provider
from .services import async_register_services

_DATA_FEEDBACK = "feedback_registry"

type OpenDataConfigEntry = ConfigEntry[OpenDataCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Open Data integration and its global service API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    feedback = FeedbackRegistry(hass)
    await feedback.async_load()
    domain_data[_DATA_FEEDBACK] = feedback
    await async_register_services(hass, feedback)
    return True


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
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Unload an Open Data config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
