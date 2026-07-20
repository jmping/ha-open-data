"""Diagnostics support for Socrata Open Data."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import SocrataConfigEntry
from .const import CONF_DATASET_ID, CONF_PORTAL_URL, CONF_TIMESTAMP_FIELD


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SocrataConfigEntry
) -> dict[str, Any]:
    """Return diagnostics without exposing source-row values."""
    coordinator = entry.runtime_data
    data = coordinator.data
    row = data.row if data is not None else None
    metadata = coordinator.metadata

    return {
        "config_entry": {
            CONF_PORTAL_URL: entry.data[CONF_PORTAL_URL],
            CONF_DATASET_ID: entry.data[CONF_DATASET_ID],
            CONF_TIMESTAMP_FIELD: entry.data.get(CONF_TIMESTAMP_FIELD),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "retrieved_at": (
                data.retrieved_at.isoformat() if data is not None else None
            ),
            "source_row_present": row is not None,
            "source_row_fields": sorted(row) if row is not None else [],
        },
        "dataset": {
            "name": metadata.name if metadata is not None else None,
            "description": metadata.description if metadata is not None else None,
        },
    }
