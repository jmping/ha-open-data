"""Tests for options reconciliation after role and structure changes."""

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


records = _load("record_structure")
reconciliation = _load("options_reconciliation")


def _available():
    configured = records.build_record_structure(unit_key_fields=("station",))
    return configured, records.build_record_selections(
        [{"station": "A"}, {"station": "A"}, {"station": "B"}], configured
    )


def test_missing_selection_defaults_to_all_deduplicated_units() -> None:
    configured, available = _available()

    result = reconciliation.reconcile_options(
        raw_records=None,
        records_were_configured=False,
        available_records=available,
        unit_key_fields=configured.unit_key_fields,
        raw_fields=None,
        fields_were_configured=False,
        available_fields=("pm2_5", "no2"),
    )

    assert len(result.selected_records) == 2
    assert set(result.selected_fields) == {"pm2_5", "no2"}


def test_explicit_empty_selections_remain_empty() -> None:
    configured, available = _available()

    result = reconciliation.reconcile_options(
        raw_records=[],
        records_were_configured=True,
        available_records=available,
        unit_key_fields=configured.unit_key_fields,
        raw_fields=[],
        fields_were_configured=True,
        available_fields=("pm2_5", "no2"),
    )

    assert result.selected_records == ()
    assert result.selected_fields == ()


def test_legacy_single_key_values_migrate_and_stale_values_are_pruned() -> None:
    configured, available = _available()

    result = reconciliation.reconcile_options(
        raw_records=("A", "A", "missing"),
        records_were_configured=True,
        available_records=available,
        unit_key_fields=configured.unit_key_fields,
        raw_fields=("pm2_5", "removed"),
        fields_were_configured=True,
        available_fields=("pm2_5", "no2"),
    )

    assert len(result.selected_records) == 1
    assert records.decode_unit_key(
        result.selected_records[0], configured.unit_key_fields
    ) == {"station": "A"}
    assert result.selected_fields == ("pm2_5",)


def test_changed_identity_rebuilds_choices_and_drops_old_numeric_values() -> None:
    old_structure = records.build_record_structure(unit_key_fields=("longitude",))
    old_selection = records.build_record_selections(
        [{"longitude": "-56.26"}], old_structure
    )[0].value

    new_structure = records.build_record_structure(unit_key_fields=("location_name",))
    available = records.build_record_selections(
        [
            {"location_name": "North Beach"},
            {"location_name": "South Beach"},
        ],
        new_structure,
    )

    result = reconciliation.reconcile_options(
        raw_records=(old_selection,),
        records_were_configured=True,
        available_records=available,
        unit_key_fields=new_structure.unit_key_fields,
        raw_fields=("temperature",),
        fields_were_configured=True,
        available_fields=("temperature",),
    )

    assert result.selected_records == ()
    assert all("-56.26" not in value for value in result.selected_records)


def test_changed_display_retains_only_values_present_in_regenerated_choices() -> None:
    structure = records.build_record_structure(unit_key_fields=("station",))
    old_available = records.build_record_selections(
        [{"station": "A"}, {"station": "B"}], structure
    )
    selected_a, selected_b = (item.value for item in old_available)
    new_available = records.build_record_selections(
        [{"station": "A", "display": "Alpha Station"}], structure
    )

    result = reconciliation.reconcile_options(
        raw_records=(selected_a, selected_b),
        records_were_configured=True,
        available_records=new_available,
        unit_key_fields=structure.unit_key_fields,
        raw_fields=(),
        fields_were_configured=True,
        available_fields=(),
    )

    assert result.selected_records == (selected_a,)
