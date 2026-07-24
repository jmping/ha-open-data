"""Exercise setup, reload, and unload using a real Home Assistant config entry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.open_data import (
    DATA_REANALYSIS_CONTROLLERS,
    DATA_SUPPRESS_RELOAD,
    _async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.open_data.const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    DOMAIN,
)
from custom_components.open_data.models import OpenDataDataset, OpenDataSnapshot

pytestmark = pytest.mark.asyncio


class _FakeCoordinator:
    """Minimal coordinator contract consumed by config-entry setup."""

    def __init__(self, snapshot: OpenDataSnapshot) -> None:
        self.data = snapshot
        self.first_refresh_calls = 0
        self.listeners = []

    async def async_config_entry_first_refresh(self) -> None:
        self.first_refresh_calls += 1

    def async_add_listener(self, listener):
        self.listeners.append(listener)
        return lambda: None


class _FakeController:
    """Track reanalysis ownership without running analysis logic."""

    instances = []

    def __init__(self, hass, entry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.async_run = AsyncMock()
        self.instances.append(self)


async def test_setup_reload_and_unload_preserve_entry_ownership(hass) -> None:
    """Runtime data and controller ownership are created and cleaned predictably."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_PROVIDER: "ckan",
            CONF_PORTAL_URL: "https://data.example.gov",
            CONF_DATASET_ID: "weather",
        },
    )
    entry.add_to_hass(hass)
    hass.data[DOMAIN] = {
        DATA_REANALYSIS_CONTROLLERS: {},
        DATA_SUPPRESS_RELOAD: set(),
    }

    snapshot = OpenDataSnapshot(
        dataset=OpenDataDataset(dataset_id="weather", title="Weather"),
        values={"temperature": 20},
    )
    coordinator = _FakeCoordinator(snapshot)
    _FakeController.instances.clear()

    with (
        patch("custom_components.open_data.create_provider", return_value=MagicMock()),
        patch("custom_components.open_data.async_get_clientsession", return_value=MagicMock()),
        patch("custom_components.open_data.OpenDataCoordinator", return_value=coordinator),
        patch(
            "custom_components.open_data.async_prune_deselected_record_devices",
            new=AsyncMock(),
        ) as prune,
        patch("custom_components.open_data.ReanalysisController", _FakeController),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_reload",
            new=AsyncMock(return_value=True),
        ) as reload_entry,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ) as unload_platforms,
    ):
        assert await async_setup_entry(hass, entry) is True
        await hass.async_block_till_done()

        assert entry.runtime_data is coordinator
        assert coordinator.first_refresh_calls == 1
        assert len(coordinator.listeners) == 1
        assert (
            hass.data[DOMAIN][DATA_REANALYSIS_CONTROLLERS][entry.entry_id]
            is _FakeController.instances[0]
        )
        forward.assert_awaited_once()
        prune.assert_awaited_once()

        await _async_reload_entry(hass, entry)
        reload_entry.assert_awaited_once_with(entry.entry_id)

        assert await async_unload_entry(hass, entry) is True
        unload_platforms.assert_awaited_once()
        assert entry.entry_id not in hass.data[DOMAIN][DATA_REANALYSIS_CONTROLLERS]
