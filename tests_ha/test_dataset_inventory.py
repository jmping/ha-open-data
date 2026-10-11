"""Regression coverage for persistent inventory independent of HA activation."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.open_data.dataset_inventory import (
    DatasetInventory,
    dataset_key,
    source_key,
)


def _entry(dataset_id="weather", *, resource_id=None):
    data = {
        "provider": "ckan",
        "portal_url": "https://ckan.a2gov.org",
        "dataset_id": dataset_id,
        "selected_fields": ["temperature"],
    }
    if resource_id:
        data["resource_id"] = resource_id
    return {
        "unique_id": f"ckan:https://ckan.a2gov.org:{dataset_id}:{resource_id or ''}",
        "title": dataset_id,
        "data": data,
    }


@pytest.fixture
def storage():
    """Use an in-memory persistence double that survives registry recreation."""
    stored = {}
    store = Mock()
    store.async_load = AsyncMock(side_effect=lambda: deepcopy(stored))

    async def save(data):
        stored.clear()
        stored.update(deepcopy(data))

    store.async_save = AsyncMock(side_effect=save)
    return store


async def test_prepared_dataset_survives_restart_without_entities(hass, storage):
    with patch("custom_components.open_data.dataset_inventory.Store", return_value=storage):
        first = DatasetInventory(hass)
        await first.async_load()
        await first.async_save_prepared(_entry())
        assert len(first.sources()) == 1
        assert len(first.datasets()) == 1
        assert first.datasets()[0].status == "ready"
        assert not hass.config_entries.async_entries("open_data")

        restored = DatasetInventory(hass)
        await restored.async_load()
        result = restored.get_dataset("ckan", "https://ckan.a2gov.org", "weather")
        assert result is not None
        assert result.prepared == _entry()
        assert result.status == "ready"
        assert not hass.config_entries.async_entries("open_data")


async def test_multiple_datasets_and_resources_share_source(hass, storage):
    with patch("custom_components.open_data.dataset_inventory.Store", return_value=storage):
        inventory = DatasetInventory(hass)
        await inventory.async_load()
        await inventory.async_save_prepared(_entry("weather"))
        await inventory.async_save_prepared(_entry("pfas", resource_id="sample-a"))
        await inventory.async_save_prepared(_entry("pfas", resource_id="sample-b"))
        await inventory.async_save_prepared(_entry("weather"))
        assert len(inventory.sources()) == 1
        assert len(inventory.datasets()) == 3
        assert len({item.key for item in inventory.datasets()}) == 3
        assert source_key("CKAN", "https://CKAN.A2GOV.ORG/") == source_key(
            "ckan", "https://ckan.a2gov.org"
        )
        assert dataset_key("portal", "pfas", "a") != dataset_key("portal", "pfas", "b")


async def test_failed_repreparation_preserves_previous_payload(hass, storage):
    with patch("custom_components.open_data.dataset_inventory.Store", return_value=storage):
        inventory = DatasetInventory(hass)
        await inventory.async_load()
        await inventory.async_save_prepared(_entry())
        await inventory.async_register_dataset(
            "ckan", "https://ckan.a2gov.org", "weather", None, "weather",
            status="failed", error="timeout",
        )
        result = inventory.get_dataset("ckan", "https://ckan.a2gov.org", "weather")
        assert result is not None
        assert result.status == "failed"
        assert result.error == "timeout"
        assert result.prepared == _entry()


async def test_activation_changes_status_but_retains_prepared_snapshot(hass, storage):
    with patch("custom_components.open_data.dataset_inventory.Store", return_value=storage):
        inventory = DatasetInventory(hass)
        await inventory.async_load()
        await inventory.async_save_prepared(_entry())
        await inventory.async_mark_activated(_entry())
        result = inventory.get_dataset("ckan", "https://ckan.a2gov.org", "weather")
        assert result is not None
        assert result.status == "activated"
        assert result.prepared == _entry()


async def test_reject_oversized_payload_without_mutation(hass, storage):
    with patch("custom_components.open_data.dataset_inventory.Store", return_value=storage):
        inventory = DatasetInventory(hass)
        await inventory.async_load()
        oversized = _entry()
        oversized["data"]["raw"] = "x" * 200_000
        with pytest.raises(ValueError, match="storage bounds"):
            await inventory.async_save_prepared(oversized)
        assert inventory.datasets() == ()


async def test_payload_is_defensively_copied(hass, storage):
    with patch("custom_components.open_data.dataset_inventory.Store", return_value=storage):
        inventory = DatasetInventory(hass)
        await inventory.async_load()
        entry = _entry()
        await inventory.async_save_prepared(entry)
        entry["data"]["selected_fields"].append("wind_speed")
        found = inventory.get_dataset("ckan", "https://ckan.a2gov.org", "weather")
        assert found is not None
        assert found.prepared["data"]["selected_fields"] == ["temperature"]
