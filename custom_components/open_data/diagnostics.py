"""Diagnostics for Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import OpenDataCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry[OpenDataCoordinator]
) -> dict[str, Any]:
    """Return non-row diagnostics for a config entry."""
    coordinator = entry.runtime_data
    dataset = coordinator.data.dataset
    return {
        "config": dict(entry.data),
        "provider": coordinator.provider.provider_name,
        "dataset": {
            "id": dataset.dataset_id,
            "title": dataset.title,
            "resource_id": dataset.resource_id,
            "field_count": len(dataset.fields),
            "fields": [field.name for field in dataset.fields],
        },
        "last_update_success": coordinator.last_update_success,
        "row_available": bool(coordinator.data.values),
    }
