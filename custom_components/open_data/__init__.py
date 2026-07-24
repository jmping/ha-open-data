"""Open Data integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DATASET_ID,
    CONF_DISPLAY_FIELD,
    CONF_FIELD_ROLES,
    CONF_HIERARCHY_FIELDS,
    CONF_IDENTITY_FIELD,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RECORD_STRUCTURE,
    CONF_RESOURCE_ID,
    CONF_SELECTED_RECORDS,
    CONF_SELECTED_FIELDS,
    CONF_TIMESTAMP_FIELD,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import OpenDataCoordinator
from .entity_identity import effective_identity_field, normalize_selected_records
from .feedback import FeedbackRegistry
from .providers import create_provider
from .preparation import DATA_PREPARATIONS, PreparationRegistry
from .reanalysis_runtime import (
    DATA_REANALYSIS_CONTROLLERS,
    DATA_SUPPRESS_RELOAD,
    ReanalysisController,
)
from .reanalysis_service import async_register_reanalysis_service
from .record_structure import legacy_record_structure, load_record_structure
from .registry_reconciliation import async_prune_deselected_record_devices
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_DATA_FEEDBACK = "feedback_registry"

type OpenDataConfigEntry = ConfigEntry[OpenDataCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Open Data integration and its global service API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    feedback = FeedbackRegistry(hass)
    await feedback.async_load()
    domain_data[_DATA_FEEDBACK] = feedback
    preparations = PreparationRegistry(hass)
    await preparations.async_load()
    domain_data[DATA_PREPARATIONS] = preparations
    domain_data.setdefault(DATA_REANALYSIS_CONTROLLERS, {})
    domain_data.setdefault(DATA_SUPPRESS_RELOAD, set())
    await async_register_services(hass, feedback)
    await async_register_reanalysis_service(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Add an explicit record structure without invalidating old selections."""
    if entry.version >= 2:
        return True
    data = dict(entry.data)
    if CONF_RECORD_STRUCTURE not in data:
        data[CONF_RECORD_STRUCTURE] = legacy_record_structure(
            data.get(CONF_IDENTITY_FIELD),
            data.get(CONF_DISPLAY_FIELD),
            data.get(CONF_TIMESTAMP_FIELD),
        ).as_dict()
    hass.config_entries.async_update_entry(entry, data=data, version=2)
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
    selected_records = normalize_selected_records(raw_records)

    configured_identity = entry.options.get(CONF_IDENTITY_FIELD) or entry.data.get(
        CONF_IDENTITY_FIELD
    )
    configured_display = entry.options.get(CONF_DISPLAY_FIELD) or entry.data.get(
        CONF_DISPLAY_FIELD
    )
    identity_field = effective_identity_field(configured_identity, configured_display)

    if identity_field != configured_identity:
        selected_records = ()
        repaired_options = dict(entry.options)
        repaired_options[CONF_IDENTITY_FIELD] = identity_field
        repaired_options[CONF_SELECTED_RECORDS] = []
        hass.config_entries.async_update_entry(entry, options=repaired_options)

    coordinator = OpenDataCoordinator(
        hass,
        provider,
        entry.data[CONF_DATASET_ID],
        entry.data.get(CONF_RESOURCE_ID),
        entry.options.get(CONF_TIMESTAMP_FIELD)
        or entry.data.get(CONF_TIMESTAMP_FIELD)
        or None,
        identity_field,
        configured_display,
        selected_records,
        tuple(entry.data.get(CONF_HIERARCHY_FIELDS, ())),
        load_record_structure(
            entry.options.get(
                CONF_RECORD_STRUCTURE, entry.data.get(CONF_RECORD_STRUCTURE)
            )
        ),
        dict(
            entry.options.get(CONF_FIELD_ROLES, entry.data.get(CONF_FIELD_ROLES, {}))
        ),
        (
            tuple(entry.options[CONF_SELECTED_FIELDS])
            if CONF_SELECTED_FIELDS in entry.options
            else (
                tuple(entry.data[CONF_SELECTED_FIELDS])
                if CONF_SELECTED_FIELDS in entry.data
                else None
            )
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    snapshot = coordinator.data
    if snapshot is not None:
        dataset = snapshot.dataset
        resource = dataset.resource_id or "default"
        base_identifier = (
            f"{entry.data[CONF_PROVIDER]}:{entry.data[CONF_PORTAL_URL]}:"
            f"{dataset.dataset_id}:{resource}"
        )
        await async_prune_deselected_record_devices(
            hass,
            entry_id=entry.entry_id,
            base_identifier=base_identifier,
            selected_records=selected_records,
        )

    controller = ReanalysisController(hass, entry, coordinator)
    hass.data[DOMAIN][DATA_REANALYSIS_CONTROLLERS][entry.entry_id] = controller

    def _schedule_reanalysis() -> None:
        hass.async_create_task(
            controller.async_run(),
            f"Check open data analysis for {entry.entry_id}",
        )

    entry.async_on_unload(coordinator.async_add_listener(_schedule_reanalysis))
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _schedule_reanalysis()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenDataConfigEntry) -> bool:
    """Unload an Open Data config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).get(DATA_REANALYSIS_CONTROLLERS, {}).pop(
            entry.entry_id, None
        )
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry after user-facing options change."""
    suppressed = hass.data.get(DOMAIN, {}).get(DATA_SUPPRESS_RELOAD, set())
    if entry.entry_id in suppressed:
        suppressed.discard(entry.entry_id)
        return
    await hass.config_entries.async_reload(entry.entry_id)
