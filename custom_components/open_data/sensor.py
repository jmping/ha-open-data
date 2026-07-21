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
    CONF_IGNORED_FIELDS,
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

    ignored = set(entry.data.get(CONF_IGNORED_FIELDS, ()))
    choices = tuple(field for field in snapshot.dataset.fields if field.name not in ignored)
    selected = set(entry.options.get(CONF_SELECTED_FIELDS, ()))
    fields = tuple(field for field in choices if not selected or field.name in selected)
    mappings = {
        item["source_field"]: item
        for item in entry.data.get(CONF_FIELD_MAPPINGS, [])
        if isinstance(item, dict)
        and isinstance(item.get("source_field"), str)
        and isinstance(item.get("canonical_metric"), str)
    }

    entities: list[SensorEntity] = []
    if snapshot.records:
        for record_id in snapshot.records:
            entities.append(OpenDataStatusSensor(entry, coordinator, record_id))
            entities.extend(
                OpenDataFieldSensor(
                    entry,
                    coordinator,
                    field.name,
                    field.label,
                    mappings.get(field.name),
                    record_id,
                )
                for field in fields
            )
    else:
        entities.append(OpenDataStatusSensor(entry, coordinator))
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

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        record_id: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        snapshot = coordinator.data
        if snapshot is None:
            raise ValueError("Open Data coordinator has no initial snapshot")
        dataset = snapshot.dataset
        provider = entry.data[CONF_PROVIDER]
        portal = entry.data[CONF_PORTAL_URL]
        resource = dataset.resource_id or "default"
        base_identifier = f"{provider}:{portal}:{dataset.dataset_id}:{resource}"
        self._record_id = record_id
        self._identifier = (
            f"{base_identifier}:record:{record_id}" if record_id is not None else base_identifier
        )
        profile_id = entry.data.get(CONF_PROFILE_ID)
        model = (
            f"Open data {profile_id.replace('_', ' ')}"
            if profile_id
            else "Open data dataset"
        )
        label = snapshot.record_labels.get(record_id, record_id) if record_id else None
        device_name = f"{dataset.title} — {label}" if label else dataset.title
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._identifier)},
            name=device_name,
            manufacturer=provider.upper(),
            model=model,
            configuration_url=portal,
        )

    def _record_values(self) -> dict[str, Any]:
        snapshot = self.coordinator.data
        if snapshot is None:
            return {}
        if self._record_id is None:
            return snapshot.values
        return snapshot.records.get(self._record_id, {})


class OpenDataStatusSensor(OpenDataSensorBase):
    """Expose whether the dataset or selected record returned a row."""

    _attr_translation_key = "dataset_status"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        record_id: str | None = None,
    ) -> None:
        super().__init__(entry, coordinator, record_id)
        self._attr_unique_id = f"{self._identifier}:status"

    @property
    def native_value(self) -> str:
        return "data_available" if self._record_values() else "no_data"


class OpenDataFieldSensor(OpenDataSensorBase):
    """Expose one field from the latest row for a dataset or selected record."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        field_name: str,
        field_label: str,
        mapping: dict[str, Any] | None = None,
        record_id: str | None = None,
    ) -> None:
        super().__init__(entry, coordinator, record_id)
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
        native_unit = definition.metadata.get("native_unit_of_measurement")
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
        if native_unit:
            self._attr_native_unit_of_measurement = native_unit
        self._attr_extra_state_attributes = {
            "canonical_metric": canonical_metric,
            "mapping_method": mapping.get("mapping_method", "synonym"),
            "mapping_confidence": mapping.get("confidence"),
        }
        if record_id is not None:
            self._attr_extra_state_attributes["record_id"] = record_id

    @property
    def native_value(self) -> Any:
        value = self._record_values().get(self._field_name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)[:255]
