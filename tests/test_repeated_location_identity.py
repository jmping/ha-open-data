"""Regression tests for repeated locations with unique observation rows."""

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
    path = _ROOT.joinpath(*name.split("."))
    if path.is_dir():
        path = path / "__init__.py"
    else:
        path = path.with_suffix(".py")
    spec = spec_from_file_location(f"custom_components.open_data.{name}", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


models = _load("models")
_load("ontology")
analyzer = _load("analyzer")
OpenDataDataset = models.OpenDataDataset
OpenDataField = models.OpenDataField


def test_beach_name_beats_unique_measurement_id() -> None:
    dataset = OpenDataDataset(
        dataset_id="beach-water-quality",
        title="Beach Water Quality - Automated Sensors",
        fields=(
            OpenDataField("measurement_id", "Measurement ID"),
            OpenDataField("beach_name", "Beach Name"),
            OpenDataField("measurement_timestamp", "Measurement Timestamp"),
            OpenDataField("turbidity", "Turbidity"),
        ),
    )
    rows = [
        {
            "measurement_id": f"63rdStreetBeach{hour:02d}00",
            "beach_name": "63rd Street Beach",
            "measurement_timestamp": f"2026-07-20T{hour:02d}:00:00Z",
            "turbidity": 1.0 + hour,
        }
        for hour in range(10, 16)
    ]

    structure = analyzer.analyze_dataset(dataset, rows)

    assert structure.identity_field == "beach_name"
    assert structure.display_field != "measurement_timestamp"
    assert structure.timestamp_field == "measurement_timestamp"


def test_selectable_beaches_are_deduplicated_by_stable_identity() -> None:
    dataset = OpenDataDataset(
        dataset_id="beaches",
        title="Beach Observations",
        fields=(
            OpenDataField("beach_name", "Beach Name"),
            OpenDataField("observed_at", "Observed At"),
            OpenDataField("temperature", "Temperature"),
        ),
    )
    rows = [
        {"beach_name": "63rd Street Beach", "observed_at": "2026-07-20T10:00:00Z"},
        {"beach_name": "63rd Street Beach", "observed_at": "2026-07-20T11:00:00Z"},
        {"beach_name": "Montrose Beach", "observed_at": "2026-07-20T10:00:00Z"},
    ]
    structure = analyzer.analyze_dataset(dataset, rows)

    records = analyzer.build_selectable_records(rows, structure)

    assert [(item.value, item.label) for item in records] == [
        ("63rd Street Beach", "63rd Street Beach"),
        ("Montrose Beach", "Montrose Beach"),
    ]
