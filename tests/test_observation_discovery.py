"""Regression tests for refresh-time semantic stream discovery."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
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
discovery = _load("observation_discovery")


def _observation(
    stream_id: str,
    *,
    unit: str | None = None,
    dimensions: tuple[tuple[str, str], ...] = (),
):
    return models.SemanticObservation(
        stream_id=stream_id,
        unit_id="station-a",
        metric="temperature",
        source_field="value",
        value=20,
        unit=unit,
        dimensions=dimensions,
    )


def test_tracker_returns_only_new_streams_in_stable_order() -> None:
    tracker = discovery.ObservationStreamTracker.from_initial(
        {"existing": _observation("existing")}
    )

    assert tracker.newly_observed(
        {
            "new-b": _observation("new-b"),
            "existing": _observation("existing"),
            "new-a": _observation("new-a"),
        }
    ) == ("new-a", "new-b")
    assert tracker.newly_observed(
        {
            "new-a": _observation("new-a"),
            "new-b": _observation("new-b"),
        }
    ) == ()


def test_sparse_refresh_does_not_forget_existing_streams() -> None:
    tracker = discovery.ObservationStreamTracker.from_initial(
        {
            "temperature": _observation("temperature"),
            "humidity": _observation("humidity"),
        }
    )

    assert tracker.newly_observed({"temperature": _observation("temperature")}) == ()
    assert tracker.known_stream_ids == {"temperature", "humidity"}


def test_observation_metadata_exposes_source_unit_and_dimensions() -> None:
    attributes = discovery.observation_metadata_attributes(
        _observation(
            "northbound-speed",
            unit="km/h",
            dimensions=(("direction", "Northbound"), ("lane", "1")),
        )
    )

    assert attributes == {
        "source_unit": "km/h",
        "dimensions": {"direction": "Northbound", "lane": "1"},
    }
