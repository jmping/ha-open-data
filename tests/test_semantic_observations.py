"""Regression tests for user-directed observation materialization."""

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
roles = _load("field_roles")
records = _load("record_structure")
semantic = _load("semantic_observations")


def test_ann_arbor_wide_rows_only_emit_user_selected_data_fields() -> None:
    configured = records.build_record_structure(
        unit_key_fields=("station_id",),
        unit_label_fields=("station_name",),
        record_key_fields=("station_id", "observed_at"),
    )
    observations = semantic.normalize_observations(
        [
            {
                "station_id": "AA-1",
                "station_name": "Downtown",
                "observed_at": "2026-07-21T12:00:00Z",
                "pm2_5": 8.4,
                "no2": 11.2,
                "vendor": "Clarity",
                "rolling_mean": 7.9,
            }
        ],
        field_roles={
            "station_id": roles.FIELD_ROLE_LOCATION,
            "station_name": roles.FIELD_ROLE_DESCRIPTIVE,
            "observed_at": roles.FIELD_ROLE_TIME,
            "pm2_5": roles.FIELD_ROLE_DATA,
            "no2": roles.FIELD_ROLE_DATA,
            "vendor": roles.FIELD_ROLE_DESCRIPTIVE,
            "rolling_mean": roles.FIELD_ROLE_UNASSIGNED,
        },
        structure=configured,
    )

    assert {item.metric for item in observations.values()} == {"pm2_5", "no2"}
    assert {item.value for item in observations.values()} == {8.4, 11.2}


def test_long_rows_pivot_measurement_names_and_keep_latest_value() -> None:
    configured = records.build_record_structure(
        unit_key_fields=("station",),
        record_key_fields=("station", "observed_at", "pollutant"),
        record_label_fields=("pollutant", "observed_at"),
    )
    observations = semantic.normalize_observations(
        [
            {"station": "A", "observed_at": "2026-07-20", "pollutant": "PM2.5", "value": 5},
            {"station": "A", "observed_at": "2026-07-21", "pollutant": "PM2.5", "value": 7},
            {"station": "A", "observed_at": "2026-07-21", "pollutant": "NO2", "value": 9},
        ],
        field_roles={
            "station": roles.FIELD_ROLE_LOCATION,
            "observed_at": roles.FIELD_ROLE_TIME,
            "pollutant": roles.FIELD_ROLE_MEASUREMENT_NAME,
            "value": roles.FIELD_ROLE_DATA,
        },
        structure=configured,
    )

    by_metric = {item.metric: item for item in observations.values()}
    assert set(by_metric) == {"PM2.5", "NO2"}
    assert by_metric["PM2.5"].value == 7
    assert by_metric["PM2.5"].timestamp == "2026-07-21"


def test_selected_fields_narrow_data_without_promoting_other_roles() -> None:
    observations = semantic.normalize_observations(
        [{"station": "A", "temperature": 20, "humidity": 50}],
        field_roles={
            "station": roles.FIELD_ROLE_LOCATION,
            "temperature": roles.FIELD_ROLE_DATA,
            "humidity": roles.FIELD_ROLE_DATA,
        },
        structure=records.RecordStructure(()),
        selected_fields=("humidity", "station"),
    )

    assert [item.metric for item in observations.values()] == ["humidity"]


def test_csv_measurements_become_numeric_time_series_values() -> None:
    configured = records.build_record_structure(unit_key_fields=("station",))
    observations = semantic.normalize_observations(
        [{"station": "A", "observed_at": "2026-07-21T12:00:00Z", "pm25": "7.25"}],
        field_roles={
            "station": roles.FIELD_ROLE_LOCATION,
            "observed_at": roles.FIELD_ROLE_TIME,
            "pm25": roles.FIELD_ROLE_DATA,
        },
        structure=configured,
    )

    observation = next(iter(observations.values()))
    assert observation.value == 7.25
    assert isinstance(observation.value, float)
