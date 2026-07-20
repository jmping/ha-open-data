"""Sensor platform for Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PORTAL_URL, CONF_PROVIDER, CONF_SELECTED_FIELDS, DOMAIN
from .coordinator import OpenDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OpenDataCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors from the discovered dataset schema."""
    coordinator = entry.runtime_data
    selected = set(entry.options.get(CONF_SELECTED_FIELDS, ()))
    fields = coordinator.data.dataset.fields
    if selected:
        fields = tuple(field for field in fields if field.name in selected)
    entities: list[SensorEntity] = [OpenDataStatusSensor(entry, coordinator)]
    entities.extend(
        OpenDataFieldSensor(entry, coordinator, field.name, field.label)
        for field in fields
    )
    async_add_entities(entities)


class OpenDataSensorBase(CoordinatorEntity[OpenDataCoordinator], SensorEntity):
    """Base class for dataset sensors."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator: OpenDataCoordinator) -> None:
        super().__init__(coordinator)
        dataset = coordinator.data.dataset
        provider = entry.data[CONF_PROVIDER]
        portal = entry.data[CONF_PORTAL_URL]
        resource = dataset.resource_id or "default"
        self._identifier = f"{provider}:{portal}:{dataset.dataset_id}:{resource}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._identifier)},
            name=dataset.title,
            manufacturer=provider.upper(),
            model="Open data dataset",
            configuration_url=portal,
        )


class OpenDataStatusSensor(OpenDataSensorBase):
    """Expose whether the dataset returned a row."""

    _attr_translation_key = "dataset_status"

    def __init__(self, entry: ConfigEntry, coordinator: OpenDataCoordinator) -> None:
        super().__init__(entry, coordinator)
        self._attr_unique_id = f"{self._identifier}:status"

    @property
    def native_value(self) -> str:
        return "data_available" if self.coordinator.data.values else "no_data"


class OpenDataFieldSensor(OpenDataSensorBase):
    """Expose one field from the latest row."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        field_name: str,
        field_label: str,
    ) -> None:
        super().__init__(entry, coordinator)
        self._field_name = field_name
        self._attr_name = field_label
        self._attr_unique_id = f"{self._identifier}:{field_name}"

    @property
    def native_value(self) -> Any:
        value = self.coordinator.data.values.get(self._field_name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)[:255]
