"""Open Data integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DATASET_ID,
    CONF_ENTRY_TYPE,
    CONF_LOCATION_FIELD,
    CONF_LOCATION_VALUE,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_TIMESTAMP_FIELD,
    ENTRY_TYPE_DATASET,
    ENTRY_TYPE_PORTAL,
    PLATFORMS,
)
from .coordinator import OpenDataCoordinator
from .providers import create_provider


type OpenDataConfigEntry = ConfigEntry[OpenDataCoordinator | None]


async def async_setup_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Set up a portal index or independently updating dataset entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DATASET)
    if entry_type == ENTRY_TYPE_PORTAL:
        entry.runtime_data = None
        return True

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
        entry.options.get(CONF_LOCATION_FIELD),
        entry.options.get(CONF_LOCATION_VALUE),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Unload an Open Data entry."""
    if entry.data.get(CONF_ENTRY_TYPE, ENTRY_TYPE_DATASET) == ENTRY_TYPE_PORTAL:
        return True
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Mark legacy entries as independently updating dataset entries."""
    if entry.version == 1:
        data = {**entry.data, CONF_ENTRY_TYPE: ENTRY_TYPE_DATASET}
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
