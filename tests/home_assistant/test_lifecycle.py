"""Exercise the Open Data config-entry lifecycle in real Home Assistant."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.open_data.const import (
    CONF_DATASET_ID,
    CONF_FIELD_ROLES,
    CONF_PORTAL_URL,
    CONF_PROVIDER,
    CONF_RESOURCE_ID,
    CONF_SELECTED_FIELDS,
    CONF_TIMESTAMP_FIELD,
    DOMAIN,
)
from custom_components.open_data.models import OpenDataDataset, OpenDataField


class _FakeProvider:
    """Small deterministic provider used through the real coordinator."""

    def __init__(self) -> None:
        self.fail = False
        self.rows = [
            {
                "observed_at": "2026-07-24T12:00:00Z",
                "temperature": 20.0,
            }
        ]
        self.dataset = OpenDataDataset(
            dataset_id="weather",
            title="Lifecycle weather",
            resource_id="resource-1",
            fields=(
                OpenDataField("observed_at", "Observed at", "timestamp"),
                OpenDataField("temperature", "Temperature", "number"),
            ),
        )

    async def async_get_dataset(self, dataset_id, resource_id=None):
        return self.dataset

    async def async_observation_rows(
        self,
        dataset_id,
        resource_id,
        timestamp_field,
        *,
        filters=None,
    ):
        if self.fail:
            raise ValueError("temporary provider failure")
        return deepcopy(self.rows)


class _NoopReanalysisController:
    """Prevent unrelated background analysis from affecting lifecycle tests."""

    def __init__(self, hass, entry, coordinator) -> None:
        self.coordinator = coordinator

    async def async_run(self) -> None:
        return None


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Lifecycle weather",
        version=2,
        data={
            CONF_PROVIDER: "socrata",
            CONF_PORTAL_URL: "https://data.example.gov",
            CONF_DATASET_ID: "weather",
            CONF_RESOURCE_ID: "resource-1",
            CONF_TIMESTAMP_FIELD: "observed_at",
            CONF_SELECTED_FIELDS: ["temperature"],
            CONF_FIELD_ROLES: {
                "observed_at": "time",
                "temperature": "data",
            },
        },
    )


def _registry_unique_ids(hass: HomeAssistant, entry_id: str) -> set[str]:
    registry = er.async_get(hass)
    return {
        entity.unique_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry_id and entity.platform == DOMAIN
    }


def _registry_entity_ids(hass: HomeAssistant, entry_id: str) -> set[str]:
    registry = er.async_get(hass)
    return {
        entity.entity_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry_id and entity.platform == DOMAIN
    }


async def test_setup_refresh_failure_reload_unload_and_restart_preserve_identity(
    hass: HomeAssistant,
) -> None:
    provider = _FakeProvider()
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.open_data.create_provider",
            return_value=provider,
        ),
        patch(
            "custom_components.open_data.ReanalysisController",
            _NoopReanalysisController,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        initial_unique_ids = _registry_unique_ids(hass, entry.entry_id)
        initial_entity_ids = _registry_entity_ids(hass, entry.entry_id)
        assert any(":stream:" in unique_id for unique_id in initial_unique_ids)
        assert any(unique_id.endswith(":latest_observation") for unique_id in initial_unique_ids)
        assert all(hass.states.get(entity_id) is not None for entity_id in initial_entity_ids)

        first_coordinator = entry.runtime_data
        provider.rows = [
            {
                "observed_at": "2026-07-24T12:15:00Z",
                "temperature": 21.5,
            }
        ]
        await first_coordinator.async_request_refresh()
        await hass.async_block_till_done()
        assert first_coordinator.last_update_success is True
        assert _registry_unique_ids(hass, entry.entry_id) == initial_unique_ids

        previous_snapshot = first_coordinator.data
        provider.fail = True
        await first_coordinator.async_request_refresh()
        await hass.async_block_till_done()
        assert first_coordinator.last_update_success is False
        assert first_coordinator.data == previous_snapshot
        assert _registry_unique_ids(hass, entry.entry_id) == initial_unique_ids

        provider.fail = False
        await first_coordinator.async_request_refresh()
        await hass.async_block_till_done()
        assert first_coordinator.last_update_success is True

        hass.config_entries.async_update_entry(
            entry,
            options={"lifecycle_revision": 1},
        )
        await hass.async_block_till_done()
        assert entry.runtime_data is not first_coordinator
        assert _registry_unique_ids(hass, entry.entry_id) == initial_unique_ids

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert all(hass.states.get(entity_id) is None for entity_id in initial_entity_ids)
        assert _registry_unique_ids(hass, entry.entry_id) == initial_unique_ids

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert _registry_unique_ids(hass, entry.entry_id) == initial_unique_ids
        assert _registry_entity_ids(hass, entry.entry_id) == initial_entity_ids
