"""Sensor platform for Socrata Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DATASET_ID,
    ATTR_PORTAL_URL,
    ATTR_RETRIEVED_AT,
    ATTR_SOURCE_ROW,
    CONF_PORTAL_URL,
)
from .coordinator import SocrataDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[SocrataDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Socrata sensors from a config entry."""
    async_add_entities([SocrataDatasetStatusSensor(entry)])


class SocrataDatasetStatusSensor(
    CoordinatorEntity[SocrataDataUpdateCoordinator], SensorEntity
):
    """Diagnostic sensor for the first generic vertical slice."""

    _attr_has_entity_name = True
    _attr_name = "Dataset status"
    _attr_icon = "mdi:database-check"

    def __init__(
        self, entry: ConfigEntry[SocrataDataUpdateCoordinator]
    ) -> None:
        """Initialize the diagnostic sensor."""
        super().__init__(entry.runtime_data)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_dataset_status"

    @property
    def native_value(self) -> str:
        """Return whether a source row is present."""
        return "data available" if self.coordinator.data.row is not None else "no data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return source and provenance attributes."""
        return {
            ATTR_PORTAL_URL: self._entry.data[CONF_PORTAL_URL],
            ATTR_DATASET_ID: self.coordinator.dataset_id,
            ATTR_RETRIEVED_AT: self.coordinator.data.retrieved_at.isoformat(),
            ATTR_SOURCE_ROW: self.coordinator.data.row,
        }
