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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DISPLAY_FIELD,
    CONF_FIELD_MAPPINGS,
    CONF_IDENTITY_FIELD,
    CONF_IGNORED_FIELDS,
    CONF_LOCATION_FIELDS,
    CONF_METRIC_FIELDS,
    CONF_PORTAL_URL,
    CONF_PROFILE_ID,
    CONF_PROVIDER,
    CONF_SELECTED_FIELDS,
    CONF_TIMESTAMP_FIELD,
    CONF_TIMESTAMP_FIELDS,
    DOMAIN,
)
from .coordinator import OpenDataCoordinator
from .field_roles import classify_field_roles, context_attributes
from .ontology import metric_definitions


async def _async_prune_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    desired_unique_ids: set[str],
) -> None:
    """Remove entities and orphaned devices no longer selected by this entry."""
    entity_registry = er.async_get(hass)
    stale = [
        entity
        for entity in entity_registry.entities.values()
        if entity.config_entry_id == entry.entry_id
        and entity.platform == DOMAIN
        and entity.unique_id not in desired_unique_ids
    ]
    stale_device_ids = {entity.device_id for entity in stale if entity.device_id}
    for entity in stale:
        entity_registry.async_remove(entity.entity_id)

    if not stale_device_ids:
        return

    remaining_device_ids = {
        entity.device_id
        for entity in entity_registry.entities.values()
        if entity.device_id is not None
    }
    device_registry = dr.async_get(hass)
    for device_id in stale_device_ids - remaining_device_ids:
        device = device_registry.async_get(device_id)
        if device is not None and entry.entry_id in device.config_entries:
            device_registry.async_remove_device(device_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OpenDataCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create measurement sensors while retaining descriptive source context."""
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    if snapshot is None:
        return

    ignored = set(entry.data.get(CONF_IGNORED_FIELDS, ()))
    mappings = {
        item["source_field"]: item
        for item in entry.data.get(CONF_FIELD_MAPPINGS, [])
        if isinstance(item, dict)
        and isinstance(item.get("source_field"), str)
        and isinstance(item.get("canonical_metric"), str)
    }
    configured_metrics = set(entry.data.get(CONF_METRIC_FIELDS, ())) | set(mappings)
    structural_fields = {
        entry.options.get(CONF_IDENTITY_FIELD) or entry.data.get(CONF_IDENTITY_FIELD),
        entry.options.get(CONF_DISPLAY_FIELD) or entry.data.get(CONF_DISPLAY_FIELD),
        *entry.data.get(CONF_LOCATION_FIELDS, ()),
    }
    structural_fields.discard(None)
    timestamp_fields = {
        entry.options.get(CONF_TIMESTAMP_FIELD) or entry.data.get(CONF_TIMESTAMP_FIELD),
        *entry.data.get(CONF_TIMESTAMP_FIELDS, ()),
    }
    timestamp_fields.discard(None)

    role_rows = list(snapshot.records.values()) if snapshot.records else [snapshot.values]
    roles = classify_field_roles(
        (field.name for field in snapshot.dataset.fields),
        role_rows,
        configured_metrics=configured_metrics,
        structural_fields=structural_fields,
        timestamp_fields=timestamp_fields,
        ignored_fields=ignored,
    )
    fields_by_name = {field.name: field for field in snapshot.dataset.fields}

    selected = set(entry.options.get(CONF_SELECTED_FIELDS, ()))
    metric_names = set(roles.metric_fields)
    if selected:
        # Options may narrow measurements, but old options cannot turn metadata
        # such as year, vendor, or station IDs back into sensors.
        metric_names &= selected
    fields = tuple(
        field for field in snapshot.dataset.fields if field.name in metric_names
    )

    # If classification cannot identify a metric, keep source context available
    # on valid status sensors rather than recreating every column as a sensor.
    context_fields = tuple(
        field
        for field in roles.context_fields
        if field in fields_by_name and field not in ignored
    )

    entities: list[SensorEntity] = []
    if snapshot.records:
        for record_id in snapshot.records:
            entities.append(
                OpenDataStatusSensor(entry, coordinator, record_id, context_fields)
            )
            entities.extend(
                OpenDataFieldSensor(
                    entry,
                    coordinator,
                    field.name,
                    field.label,
                    mappings.get(field.name),
                    record_id,
                    context_fields,
                )
                for field in fields
            )
    elif not (coordinator.identity_field and coordinator.selected_records):
        # A configured record selection with no returned observations should
        # produce zero entities, not a misleading dataset-level empty entity.
        entities.append(OpenDataStatusSensor(entry, coordinator, None, context_fields))
        entities.extend(
            OpenDataFieldSensor(
                entry,
                coordinator,
                field.name,
                field.label,
                mappings.get(field.name),
                None,
                context_fields,
            )
            for field in fields
        )

    desired_unique_ids = {
        entity.unique_id for entity in entities if entity.unique_id is not None
    }
    await _async_prune_stale_entities(hass, entry, desired_unique_ids)
    if entities:
        async_add_entities(entities)


class OpenDataSensorBase(CoordinatorEntity[OpenDataCoordinator], SensorEntity):
    """Base class for dataset sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        record_id: str | None = None,
        context_fields: tuple[str, ...] = (),
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
        self._context_fields = context_fields
        self._dataset_title = dataset.title
        self._provider = provider
        self._portal = portal
        self._resource_id = dataset.resource_id
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

    def _source_attributes(self) -> dict[str, Any]:
        """Return context that explains what this entity represents."""
        attributes: dict[str, Any] = {
            "dataset": self._dataset_title,
            "provider": self._provider,
            "source_url": self._portal,
        }
        if self._resource_id:
            attributes["resource_id"] = self._resource_id
        if self._record_id is not None:
            attributes["record_id"] = self._record_id
            snapshot = self.coordinator.data
            if snapshot is not None:
                attributes["record_label"] = snapshot.record_labels.get(
                    self._record_id, self._record_id
                )
        attributes.update(
            context_attributes(self._record_values(), self._context_fields)
        )
        return attributes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._source_attributes()


class OpenDataStatusSensor(OpenDataSensorBase):
    """Expose whether the dataset or selected record returned a row."""

    _attr_translation_key = "dataset_status"

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        record_id: str | None = None,
        context_fields: tuple[str, ...] = (),
    ) -> None:
        super().__init__(entry, coordinator, record_id, context_fields)
        self._attr_unique_id = f"{self._identifier}:status"

    @property
    def native_value(self) -> str:
        return "data_available" if self._record_values() else "no_data"


class OpenDataFieldSensor(OpenDataSensorBase):
    """Expose one measurement from the latest row."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: OpenDataCoordinator,
        field_name: str,
        field_label: str,
        mapping: dict[str, Any] | None = None,
        record_id: str | None = None,
        context_fields: tuple[str, ...] = (),
    ) -> None:
        super().__init__(entry, coordinator, record_id, context_fields)
        self._field_name = field_name
        self._mapping_attributes: dict[str, Any] = {}
        self._attr_name = field_label
        self._attr_unique_id = f"{self._identifier}:{field_name}"

        if mapping is None:
            return
        canonical_metric = mapping["canonical_metric"]
        definition = metric_definitions().get(canonical_metric)
        if definition is not None:
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
        self._mapping_attributes = {
            "canonical_metric": canonical_metric,
            "mapping_method": mapping.get("mapping_method", "synonym"),
            "mapping_confidence": mapping.get("confidence"),
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = self._source_attributes()
        attributes.update(self._mapping_attributes)
        return attributes

    @property
    def native_value(self) -> Any:
        value = self._record_values().get(self._field_name)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)[:255]
