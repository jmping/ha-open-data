"""Reconcile Home Assistant registries after record-selection changes."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN


def record_id_from_identifiers(
    identifiers: Iterable[tuple[str, str]], base_identifier: str
) -> str | None:
    """Extract this integration's record ID from a device identifier set."""
    prefix = f"{base_identifier}:record:"
    for domain, identifier in identifiers:
        if domain == DOMAIN and identifier.startswith(prefix):
            return identifier[len(prefix) :]
    return None


async def async_prune_deselected_record_devices(
    hass: HomeAssistant,
    *,
    entry_id: str,
    base_identifier: str,
    selected_records: Iterable[str],
) -> tuple[int, int]:
    """Remove entities and orphan devices for records no longer selected.

    Reconciliation is deliberately device-scoped. It does not compare the current
    provider response with the entity registry, so a sparse or failed refresh cannot
    remove entities belonging to a record that remains selected.
    """
    selected = {str(record_id) for record_id in selected_records}
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    stale_device_ids = {
        device.id
        for device in device_registry.devices.values()
        if entry_id in device.config_entries
        and (record_id := record_id_from_identifiers(device.identifiers, base_identifier))
        is not None
        and record_id not in selected
    }

    removed_entities = 0
    for entity in tuple(entity_registry.entities.values()):
        if (
            entity.config_entry_id == entry_id
            and entity.platform == DOMAIN
            and entity.device_id in stale_device_ids
        ):
            entity_registry.async_remove(entity.entity_id)
            removed_entities += 1

    remaining_device_ids = {
        entity.device_id
        for entity in entity_registry.entities.values()
        if entity.device_id is not None
    }
    removed_devices = 0
    for device_id in stale_device_ids - remaining_device_ids:
        device = device_registry.async_get(device_id)
        if device is not None and entry_id in device.config_entries:
            device_registry.async_remove_device(device_id)
            removed_devices += 1

    return removed_entities, removed_devices
