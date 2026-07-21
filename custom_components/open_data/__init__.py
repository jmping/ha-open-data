"""Open Data integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DATASET_ID,
    CONF_DISPLAY_FIELD,
    CONF_HIERARCHY_FIELDS,
    CONF_IDENTITY_FIELD,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_SELECTED_RECORDS,
    CONF_TIMESTAMP_FIELD,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import OpenDataCoordinator
from .entity_identity import effective_identity_field
from .feedback import FeedbackRegistry
from .providers import create_provider
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_DATA_FEEDBACK = "feedback_registry"

type OpenDataConfigEntry = ConfigEntry[OpenDataCoordinator]


def _normalize_selected_records(raw_records: object) -> tuple[str, ...]:
    """Return distinct, non-empty selector values in their saved order."""
    if isinstance(raw_records, str):
        candidates = (raw_records,)
    elif isinstance(raw_records, (list, tuple, set, frozenset)):
        candidates = raw_records
    else:
        return ()
    return tuple(
        dict.fromkeys(
            value
            for item in candidates
            if (value := str(item).strip())
        )
    )


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
    raw_records = entry.options.get(
        CONF_SELECTED_RECORDS, entry.data.get(CONF_SELECTED_RECORDS, ())
    )
    selected_records = _normalize_selected_records(raw_records)

    configured_identity = entry.options.get(CONF_IDENTITY_FIELD) or entry.data.get(
        CONF_IDENTITY_FIELD
    )
    configured_display = entry.options.get(CONF_DISPLAY_FIELD) or entry.data.get(
        CONF_DISPLAY_FIELD
    )
    identity_field = effective_identity_field(configured_identity, configured_display)
    display_field = configured_display if configured_display != identity_field else None

    # Record values saved under an observation ID cannot be reused after repairing
    # the identity to a stable place name. Let the user select the desired places
    # from the rebuilt options flow instead of issuing invalid per-row queries.
    if identity_field != configured_identity or identity_field is None:
        selected_records = ()

    coordinator = OpenDataCoordinator(
        hass,
        provider,
        entry.data[CONF_DATASET_ID],
        entry.data.get(CONF_RESOURCE_ID),
        entry.options.get(CONF_TIMESTAMP_FIELD)
        or entry.data.get(CONF_TIMESTAMP_FIELD)
        or None,
        identity_field,
        display_field,
        selected_records,
        tuple(entry.data.get(CONF_HIERARCHY_FIELDS, ())),
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
