"""Regression tests for record-selection registry reconciliation."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
DOMAIN = "open_data"

package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules["custom_components.open_data"] = package

const = ModuleType("custom_components.open_data.const")
const.DOMAIN = DOMAIN
sys.modules["custom_components.open_data.const"] = const

core = ModuleType("homeassistant.core")
core.HomeAssistant = object
sys.modules["homeassistant.core"] = core

helpers = sys.modules.setdefault("homeassistant.helpers", ModuleType("homeassistant.helpers"))
device_registry = ModuleType("homeassistant.helpers.device_registry")
entity_registry = ModuleType("homeassistant.helpers.entity_registry")
helpers.device_registry = device_registry
helpers.entity_registry = entity_registry
sys.modules["homeassistant.helpers.device_registry"] = device_registry
sys.modules["homeassistant.helpers.entity_registry"] = entity_registry

spec = spec_from_file_location(
    "custom_components.open_data.registry_reconciliation",
    _ROOT / "registry_reconciliation.py",
)
assert spec is not None and spec.loader is not None
reconciliation = module_from_spec(spec)
sys.modules[spec.name] = reconciliation
spec.loader.exec_module(reconciliation)


class FakeEntityRegistry:
    def __init__(self, entities):
        self.entities = {entity.entity_id: entity for entity in entities}

    def async_remove(self, entity_id):
        self.entities.pop(entity_id)


class FakeDeviceRegistry:
    def __init__(self, devices):
        self.devices = {device.id: device for device in devices}

    def async_get(self, device_id):
        return self.devices.get(device_id)

    def async_remove_device(self, device_id):
        self.devices.pop(device_id)


def _device(device_id, identifier, entry_id="entry-1"):
    return SimpleNamespace(
        id=device_id,
        identifiers={(DOMAIN, identifier)},
        config_entries={entry_id},
    )


def _entity(entity_id, device_id, entry_id="entry-1", platform=DOMAIN):
    return SimpleNamespace(
        entity_id=entity_id,
        device_id=device_id,
        config_entry_id=entry_id,
        platform=platform,
        name="User customized name",
    )


def test_record_id_extraction_preserves_colons() -> None:
    base = "ckan:https://example.test:dataset:resource"
    assert reconciliation.record_id_from_identifiers(
        {(DOMAIN, f"{base}:record:county:station-1")}, base
    ) == "county:station-1"


@pytest.mark.asyncio
async def test_prunes_only_deselected_record_entities_and_orphan_device(monkeypatch) -> None:
    base = "ckan:https://example.test:dataset:resource"
    devices = FakeDeviceRegistry(
        [
            _device("keep-device", f"{base}:record:keep"),
            _device("drop-device", f"{base}:record:drop"),
            _device("dataset-device", base),
            _device("other-entry-device", f"{base}:record:drop", "entry-2"),
        ]
    )
    entities = FakeEntityRegistry(
        [
            _entity("sensor.keep", "keep-device"),
            _entity("sensor.drop_status", "drop-device"),
            _entity("sensor.drop_metric", "drop-device"),
            _entity("sensor.freshness", "dataset-device"),
            _entity("sensor.other", "other-entry-device", "entry-2"),
        ]
    )
    monkeypatch.setattr(reconciliation.dr, "async_get", lambda hass: devices, raising=False)
    monkeypatch.setattr(reconciliation.er, "async_get", lambda hass: entities, raising=False)

    removed_entities, removed_devices = (
        await reconciliation.async_prune_deselected_record_devices(
            object(),
            entry_id="entry-1",
            base_identifier=base,
            selected_records=("keep",),
        )
    )

    assert removed_entities == 2
    assert removed_devices == 1
    assert set(entities.entities) == {
        "sensor.keep",
        "sensor.freshness",
        "sensor.other",
    }
    assert set(devices.devices) == {
        "keep-device",
        "dataset-device",
        "other-entry-device",
    }
    assert entities.entities["sensor.keep"].name == "User customized name"


@pytest.mark.asyncio
async def test_deselecting_all_removes_all_record_devices(monkeypatch) -> None:
    base = "socrata:https://example.test:abcd-1234:default"
    devices = FakeDeviceRegistry(
        [
            _device("one", f"{base}:record:one"),
            _device("two", f"{base}:record:two"),
        ]
    )
    entities = FakeEntityRegistry(
        [_entity("sensor.one", "one"), _entity("sensor.two", "two")]
    )
    monkeypatch.setattr(reconciliation.dr, "async_get", lambda hass: devices, raising=False)
    monkeypatch.setattr(reconciliation.er, "async_get", lambda hass: entities, raising=False)

    result = await reconciliation.async_prune_deselected_record_devices(
        object(),
        entry_id="entry-1",
        base_identifier=base,
        selected_records=(),
    )

    assert result == (2, 2)
    assert entities.entities == {}
    assert devices.devices == {}
