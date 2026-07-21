"""Sensor platform for Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FIELD_MAPPINGS,
    CONF_PORTAL_URL,
    CONF_PROFILE_ID,
    CONF_PROVIDER,
    CONF_SELECTED_FIELDS,
    DOMAIN,
)
from .coordinator import OpenDataCoordinator
from .ontology import metric_definitions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OpenDataCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors from the discovered dataset schema."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    if snapshot is None:
        return
    selected = set(entry.options.get(CONF_SELECTED_FIELDS, ()))
    fields = snapshot.dataset.fields
    if selected:
        fields = tuple(field for field in fields if field.name in selected)

    mappings = {
        item["source_field"]: item
        for item in entry.data.get(CONF_FIELD_MAPPINGS, [])
        if isinstance(item, dict)
        and isinstance(item.get("source_field"), str)
        and isinstance(item.get("canonical_metric"), str)
    }
    entities: list[SensorEntity] = [OpenDataStatusSensor(entry, coordinator)]
    entities.extend(
        OpenDataFieldSensor(
            entry,
            coordinator,
            field.name,
            field.label,
            mappings.get(field.name),
        )
        for field in fields
    )
    async_add_entities(entities)


class OpenDataSensorBase(CoordinatorEntity[OpenDataCoordinator], SensorEntity):
    """Base class for dataset sensors."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator: OpenDataCoordinator) -> None:
        super().__init__(coordinator)
        snapshot = coordinator.data
        if snapshot is None:
            raise ValueError("Open Data coordinator has no initial snapshot")
        dataset = snapshot.dataset
        provider = entry.data[CONF_PROVIDER]
        portal = entry.data[CONF_PORTAL_URL]
        resource = dataset.resource_id or "default"
        self._identifier = f"{provider}:{portal}:{dataset.dataset_id}:{resource}"
        profile_id = entry.data.get(CONF_PROFILE_ID)
        model = f"Open data {profile_id.replace('_', ' ')}" if profile_id else "Open data dataset"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._identifier)},
            name=dataset.title,
            manufacturer=provider.upper(),
            model=model,
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
        snapshot = self.coordinator.data
        return "data_available" if snapshot is not None and snapshot.values else "no_data"


class OpenDataFieldSensor(OpenDataSensorBase):
    """Expose one field from the latest row."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        field_name: str,
        field_label: str,
        mapping: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(entry, coordinator)
        self._field_name = field_name
        self._attr_name = field_label
        self._attr_unique_id = f"{self._identifier}:{field_name}"

        if mapping is None:
            return
        canonical_metric = mapping["canonical_metric"]
        definition = metric_definitions().get(canonical_metric)
        if definition is None:
            return
        device_class = definition.metadata.get("device_class")
        state_class = definition.metadata.get("state_class")
        try:
            if device_class:
                self._attr_device_class = SensorDeviceClass(device_class)
        except ValueError:
            pass
        try:
            if state_class:
                self._attr_state_class = SensorStateClass(state_class)
        except ValueError:
            pass
        self._attr_extra_state_attributes = {
            "canonical_metric": canonical_metric,
            "mapping_method": mapping.get("mapping_method", "synonym"),
            "mapping_confidence": mapping.get("confidence"),
        }

    @property
    def native_value(self) -> Any:
        snapshot = self.coordinator.data
        if snapshot is None:
            return None
        value = snapshot.values.get(self._field_name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)[:255]
