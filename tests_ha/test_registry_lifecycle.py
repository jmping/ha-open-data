"""Exercise entity and device registry cleanup in real Home Assistant."""

from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.open_data.const import DOMAIN
from custom_components.open_data.sensor import _async_prune_stale_entities


async def test_prune_removes_only_deselected_entities_and_orphan_devices(hass) -> None:
    """Desired identities survive while stale entities and orphan devices are removed."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    keep_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "dataset:record:keep")},
    )
    stale_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "dataset:record:stale")},
    )

    keep = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "keep-unique-id",
        config_entry=entry,
        device_id=keep_device.id,
        suggested_object_id="keep",
    )
    stale = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "stale-unique-id",
        config_entry=entry,
        device_id=stale_device.id,
        suggested_object_id="stale",
    )

    await _async_prune_stale_entities(hass, entry, {"keep-unique-id"})

    assert entity_registry.async_get(keep.entity_id) is not None
    assert entity_registry.async_get(stale.entity_id) is None
    assert device_registry.async_get(keep_device.id) is not None
    assert device_registry.async_get(stale_device.id) is None
