"""Tests for durable deferred portal preparation."""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"


def _load_module(name: str, filename: str):
    package = sys.modules.setdefault(
        "custom_components.open_data", types.ModuleType("custom_components.open_data")
    )
    package.__path__ = [str(ROOT)]
    hass = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
    hass.__path__ = []
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = object
    sys.modules["homeassistant.core"] = core
    sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
    sys.modules["homeassistant.helpers.storage"] = storage
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


preparation = _load_module("custom_components.open_data.preparation", "preparation.py")
models = sys.modules["custom_components.open_data.models"]
discovery = sys.modules["custom_components.open_data.discovery"]


def test_prepared_site_round_trip_preserves_bounded_catalog_identity() -> None:
    dataset = models.OpenDataDataset(
        dataset_id="air",
        title="Air quality",
        resource_id="csv",
        fields=(models.OpenDataField("timestamp", "Timestamp", "datetime"),),
        raw={"frequency": "hourly"},
    )
    site = preparation.PreparedSite(
        "https://data.example", "ckan", "ready", "2026-07-21T00:00:00Z",
        (discovery.score_dataset(dataset),),
    )

    restored = preparation.PreparedSite.from_dict(site.as_dict())

    assert restored.status == "ready"
    restored_dataset = restored.candidates[0].dataset
    assert restored_dataset.dataset_id == dataset.dataset_id
    assert restored_dataset.title == dataset.title
    assert restored_dataset.resource_id == dataset.resource_id
    assert restored_dataset.fields == dataset.fields
    assert restored_dataset.raw == dataset.raw


def test_prepared_site_drops_large_unneeded_provider_payloads() -> None:
    dataset = models.OpenDataDataset(
        dataset_id="large",
        title="Large ArcGIS catalog item",
        description="d" * 10_000,
        raw={
            "tags": ["weather"],
            "thumbnail_blob": "x" * 2_000_000,
            "nested_application_state": {"value": "y" * 2_000_000},
        },
    )
    site = preparation.PreparedSite(
        "https://data.example",
        "arcgis",
        "ready",
        "2026-09-05T00:00:00Z",
        (discovery.score_dataset(dataset),),
    )

    serialized = site.as_dict()

    assert len(json.dumps(serialized).encode()) < 10_000
    assert serialized["datasets"][0]["raw"] == {"tags": ["weather"]}
    assert len(serialized["datasets"][0]["description"]) == 2_000


def test_registry_persists_success_and_reuses_running_task() -> None:
    saved = []

    class FakeStore:
        async def async_save(self, value):
            saved.append(value)

    registry = object.__new__(preparation.PreparationRegistry)
    registry._store = FakeStore()
    registry._sites = {}
    registry._tasks = {}
    dataset = models.OpenDataDataset("weather", "Weather")

    async def run() -> None:
        gate = asyncio.Event()

        async def prepare():
            await gate.wait()
            return "https://data.example", "ckan", [discovery.score_dataset(dataset)]

        first = registry.start("https://data.example/", prepare)
        second = registry.start("https://DATA.example", prepare)
        assert first is second
        gate.set()
        await first

    asyncio.run(run())
    assert registry.get("https://data.example").status == "ready"
    assert saved[-1]["sites"]["https://data.example"]["status"] == "ready"


def test_interrupted_preparation_becomes_retryable_failure() -> None:
    class FakeStore:
        async def async_load(self):
            return {"sites": {"https://data.example": {
                "portal_url": "https://data.example", "provider": None,
                "status": "preparing", "updated_at": "old", "datasets": []}}}

        async def async_save(self, value):
            self.saved = value

    registry = object.__new__(preparation.PreparationRegistry)
    registry._store = FakeStore()
    registry._sites = {}
    registry._tasks = {}
    asyncio.run(registry.async_load())

    site = registry.get("https://data.example")
    assert site.status == "failed"
    assert site.error == "interrupted"


def test_old_prepared_catalog_is_rebuilt_after_discovery_changes() -> None:
    class FakeStore:
        async def async_load(self):
            return {"sites": {"https://data.example": {
                "portal_url": "https://data.example", "provider": "ckan",
                "status": "ready", "updated_at": "old", "datasets": []}}}

        async def async_save(self, value):
            self.saved = value

    registry = object.__new__(preparation.PreparationRegistry)
    registry._store = FakeStore()
    registry._sites = {}
    registry._tasks = {}
    asyncio.run(registry.async_load())

    site = registry.get("https://data.example")
    assert site.status == "failed"
    assert site.error == "catalog_schema_changed"
