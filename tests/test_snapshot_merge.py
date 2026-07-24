"""Regression tests for partial multi-record refreshes."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType


_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package


def _load(name: str):
    spec = spec_from_file_location(
        f"custom_components.open_data.{name}", _ROOT / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


models = _load("models")
snapshot_merge = _load("snapshot_merge")


def _observation(stream_id: str, unit_id: str, value: int):
    return models.SemanticObservation(
        stream_id=stream_id,
        unit_id=unit_id,
        metric="temperature",
        source_field="temperature",
        value=value,
        timestamp="2026-07-24T12:00:00Z",
    )


def _previous_snapshot():
    dataset = models.OpenDataDataset(dataset_id="weather", title="Weather")
    return models.OpenDataSnapshot(
        dataset=dataset,
        values={"station": "a", "temperature": 20},
        records={
            "a": {"station": "a", "temperature": 20},
            "b": {"station": "b", "temperature": 10},
        },
        record_labels={"a": "Station A", "b": "Station B"},
        observations={
            "a:temperature": _observation("a:temperature", "a", 20),
            "b:temperature": _observation("b:temperature", "b", 10),
        },
    )


def test_failed_record_is_carried_forward_while_sibling_updates() -> None:
    records, observations = snapshot_merge.carry_forward_failed_records(
        _previous_snapshot(),
        {"a": {"station": "a", "temperature": 21}},
        {"a:temperature": _observation("a:temperature", "a", 21)},
        ["b"],
    )

    assert records["a"]["temperature"] == 21
    assert records["b"]["temperature"] == 10
    assert observations["a:temperature"].value == 21
    assert observations["b:temperature"].value == 10


def test_successful_empty_record_is_not_carried_forward() -> None:
    records, observations = snapshot_merge.carry_forward_failed_records(
        _previous_snapshot(),
        {"a": {"station": "a", "temperature": 21}},
        {"a:temperature": _observation("a:temperature", "a", 21)},
        [],
    )

    assert "b" not in records
    assert "b:temperature" not in observations


def test_failed_record_without_previous_state_does_not_create_placeholder() -> None:
    records, observations = snapshot_merge.carry_forward_failed_records(
        _previous_snapshot(), {}, {}, ["missing"]
    )
    assert records == {}
    assert observations == {}


def test_current_result_wins_over_previous_data() -> None:
    records, observations = snapshot_merge.carry_forward_failed_records(
        _previous_snapshot(),
        {"b": {"station": "b", "temperature": 11}},
        {"b:temperature": _observation("b:temperature", "b", 11)},
        ["b"],
    )
    assert records["b"]["temperature"] == 11
    assert observations["b:temperature"].value == 11
