"""Golden runtime tests for representative open-data profiles."""

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
_FIXTURES = Path(__file__).parent / "fixtures" / "runtime_profiles"
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


_load("models")
_load("field_roles")
records = _load("record_structure")
semantic = _load("semantic_observations")


def _profiles():
    return [
        pytest.param(path, id=path.stem)
        for path in sorted(_FIXTURES.glob("*.json"))
    ]


@pytest.mark.parametrize("fixture_path", _profiles())
def test_profile_builds_deduplicated_units_and_expected_latest_streams(
    fixture_path: Path,
) -> None:
    profile = json.loads(fixture_path.read_text())
    raw_structure = profile["structure"]
    configured = records.build_record_structure(
        unit_key_fields=raw_structure["unit_key_fields"],
        unit_label_fields=raw_structure["unit_label_fields"],
        record_key_fields=raw_structure["record_key_fields"],
        record_label_fields=raw_structure["record_label_fields"],
    )
    selections = records.build_record_selections(profile["rows"], configured)

    assert len(selections) == 1
    observations = semantic.normalize_observations(
        profile["rows"],
        field_roles=profile["roles"],
        structure=configured,
        unit_id=selections[0].value,
    )

    assert sorted(item.metric for item in observations.values()) == sorted(
        profile["expected_metrics"]
    )
    assert {item.unit_id for item in observations.values()} == {selections[0].value}
    latest_time = max(row[raw_structure["record_key_fields"][-1]] for row in profile["rows"])
    assert {item.timestamp for item in observations.values()} == {latest_time}
