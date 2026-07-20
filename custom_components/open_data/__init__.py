"""Open Data integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval

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
    PROFILE_INITIAL_DELAY_SECONDS,
    PROFILE_INTERVAL_HOURS,
)
from .coordinator import OpenDataCoordinator
from .intelligence import DatasetIntelligence
from .providers import create_provider
from .providers.base import OpenDataError

_LOGGER = logging.getLogger(__name__)

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
    intelligence = DatasetIntelligence(
        hass,
        entry.entry_id,
        provider,
        entry.data[CONF_DATASET_ID],
        entry.data.get(CONF_RESOURCE_ID),
        entry.data.get(CONF_TIMESTAMP_FIELD) or None,
    )
    await intelligence.async_load()
    coordinator = OpenDataCoordinator(
        hass,
        provider,
        entry.data[CONF_DATASET_ID],
        entry.data.get(CONF_RESOURCE_ID),
        entry.data.get(CONF_TIMESTAMP_FIELD) or None,
        entry.options.get(CONF_LOCATION_FIELD),
        entry.options.get(CONF_LOCATION_VALUE),
        intelligence,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_profile() -> None:
        try:
            await intelligence.async_profile()
        except (OpenDataError, ValueError) as err:
            _LOGGER.debug("Dataset profiling deferred after provider error: %s", err)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while profiling open dataset")

    @callback
    def _schedule_profile(_now=None) -> None:
        hass.async_create_task(_async_profile())

    entry.async_on_unload(
        async_call_later(hass, PROFILE_INITIAL_DELAY_SECONDS, _schedule_profile)
    )
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _schedule_profile,
            timedelta(hours=PROFILE_INTERVAL_HOURS),
        )
    )
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
