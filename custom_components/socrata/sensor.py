"""Sensor platform for Socrata Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    ATTR_SOURCE_ROW,
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

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "dataset_status"
    _attr_icon = "mdi:database-check"

    def __init__(self, entry: SocrataConfigEntry) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(entry.runtime_data)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_dataset_status"

        metadata = self.coordinator.metadata
        dataset_name = metadata.name if metadata is not None else self.coordinator.dataset_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.dataset_id)},
            name=dataset_name,
            manufacturer="Socrata",
            model="Open Data Dataset",
            configuration_url=entry.data[CONF_PORTAL_URL],
        )

    @property
    def native_value(self) -> str:
        """Return whether a source row is present."""
        return "data_available" if self.coordinator.data.row is not None else "no_data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source and provenance attributes."""
        return {
            ATTR_PORTAL_URL: self._entry.data[CONF_PORTAL_URL],
            ATTR_DATASET_ID: self.coordinator.dataset_id,
            ATTR_RETRIEVED_AT: self.coordinator.data.retrieved_at.isoformat(),
            ATTR_SOURCE_ROW: self.coordinator.data.row,
        }
