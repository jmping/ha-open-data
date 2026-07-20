"""Composition tests for the provider-neutral planning core."""

from datetime import UTC, datetime, timedelta

from custom_components.open_data.attribute_selection import select_attributes
from custom_components.open_data.availability_planning import AvailabilityState, plan_availability
from custom_components.open_data.device_planning import plan_device
from custom_components.open_data.diagnostics_planning import PlanningDecision, build_planning_diagnostics
from custom_components.open_data.entity_planning import plan_entities
from custom_components.open_data.naming_engine import device_name, entity_name
from custom_components.open_data.observable_graph import build_observable_graph
from custom_components.open_data.observable_inference import ObservableInference
from custom_components.open_data.polling_heuristics import infer_polling_plan
from custom_components.open_data.state_selection import select_state_field
from custom_components.open_data.update_strategy import UpdateMode, infer_update_strategy


def _observables() -> tuple[ObservableInference, ...]:
    return (
        ObservableInference("temp_c", "temperature", 90, "°C", ("canonical field alias",)),
        ObservableInference("humidity", "relative_humidity", 75, "%", ("canonical label alias",)),
    )


def test_observable_entity_and_device_planning_composes() -> None:
    graph = build_observable_graph((("station-1", _observables()),))
    assert [item.kind for item in graph.for_source("station-1")] == ["temperature", "relative_humidity"]

    entities = plan_entities("station-1", graph.for_source("station-1"))
    assert {item.state_field for item in entities} == {"temp_c", "humidity"}
    device = plan_device("station-1", "Central Station", entities)
    assert device.device_key == "station-1"
    assert len(device.entity_keys) == 2


def test_update_polling_state_and_attributes_are_deterministic() -> None:
    strategy = infer_update_strategy(temporal=True, observations=True, row_count=20)
    assert strategy.mode is UpdateMode.APPEND_ONLY
    polling = infer_polling_plan(declared_seconds=10)
    assert polling.interval_seconds == 30
    state = select_state_field(_observables())
    assert state is not None and state.field == "temp_c"
    assert select_attributes(("station_id", "temp_c", "humidity", "humidity"), state_field="temp_c", excluded=("station_id",)) == ("humidity",)


def test_availability_naming_and_diagnostics() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    stale = plan_availability(observed_at=now - timedelta(minutes=20), poll_interval_seconds=300, now=now)
    assert stale.state is AvailabilityState.STALE
    assert entity_name("City Weather", "particulate_matter_2_5") == "PM2 5"
    assert device_name("Weather", "Downtown") == "Downtown Weather"

    diagnostics = build_planning_diagnostics(
        (
            PlanningDecision("state", "temp_c", ("highest-confidence observable",), ("humidity",)),
            PlanningDecision("polling", "300", ("temporal dataset",)),
        )
    )
    assert diagnostics.for_subject("state").selected == "temp_c"
