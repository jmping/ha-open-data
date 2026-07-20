"""Sensor platform for Socrata Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SocrataConfigEntry
from .const import (
    ATTR_DATASET_ID,
    ATTR_PORTAL_URL,
    ATTR_RETRIEVED_AT,
    CONF_PORTAL_URL,
    DOMAIN,
)
from .coordinator import SocrataDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SocrataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Socrata sensors from a config entry."""
    async_add_entities([SocrataDatasetStatusSensor(entry)])


class SocrataDatasetStatusSensor(
    CoordinatorEntity[SocrataDataUpdateCoordinator], SensorEntity
):
    """Diagnostic sensor for the first generic vertical slice."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "dataset_status"
    _attr_icon = "mdi:database-check"
    _attr_options = ["data_available", "no_data"]

    def __init__(self, entry: SocrataConfigEntry) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(entry.runtime_data)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_dataset_status"

        metadata = self.coordinator.metadata
        dataset_name = (
            metadata.name if metadata is not None else self.coordinator.dataset_id
        )
        device_identifier = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_identifier)},
            name=dataset_name,
            manufacturer="Socrata",
            model="Open Data Dataset",
            configuration_url=entry.data[CONF_PORTAL_URL],
        )

    @property
    def native_value(self) -> str | None:
        """Return whether a source row is present."""
        data = self.coordinator.data
        if data is None:
            return None
        return "data_available" if data.row is not None else "no_data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return compact source and provenance attributes."""
        attributes: dict[str, Any] = {
            ATTR_PORTAL_URL: self._entry.data[CONF_PORTAL_URL],
            ATTR_DATASET_ID: self.coordinator.dataset_id,
        }
        if self.coordinator.data is not None:
            attributes[ATTR_RETRIEVED_AT] = (
                self.coordinator.data.retrieved_at.isoformat()
            )
        return attributes
