"""Tests for provider-neutral adaptive sampling diagnostics."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "adaptive_sampling.py"
)
_SPEC = spec_from_file_location("open_data_adaptive_sampling", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
sampling = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = sampling
_SPEC.loader.exec_module(sampling)

DatasetOrdering = sampling.DatasetOrdering
build_retrieval_plan = sampling.build_retrieval_plan
estimate_entity_population = sampling.estimate_entity_population
infer_dataset_ordering = sampling.infer_dataset_ordering


def test_population_estimate_stays_near_observed_when_entities_repeat() -> None:
    rows = [
        {"station": station}
        for station in ("A", "B", "C")
        for _ in range(4)
    ]
    estimate = estimate_entity_population(rows, "station")
    assert estimate.observed_entities == 3
    assert estimate.estimated_entities == 3
    assert estimate.singletons == 0
    assert estimate.confidence == 1.0


def test_population_estimate_accounts_for_unseen_entities() -> None:
    rows = [
        {"station": "A"},
        {"station": "B"},
        {"station": "C"},
        {"station": "C"},
    ]
    estimate = estimate_entity_population(rows, "station")
    assert estimate.observed_entities == 3
    assert estimate.singletons == 2
    assert estimate.doubletons == 1
    assert estimate.estimated_entities == 5


def test_time_ordering_is_detected() -> None:
    ascending = [
        {"observed_at": f"2026-01-0{day}T00:00:00Z"}
        for day in range(1, 6)
    ]
    descending = list(reversed(ascending))
    assert (
        infer_dataset_ordering(ascending, None, "observed_at")
        == DatasetOrdering.TIME_ASCENDING
    )
    assert (
        infer_dataset_ordering(descending, None, "observed_at")
        == DatasetOrdering.TIME_DESCENDING
    )


def test_entity_grouping_and_random_interleaving_are_detected() -> None:
    grouped = [{"station": value} for value in ("A", "A", "A", "B", "B", "B")]
    interleaved = [{"station": value} for value in ("A", "B", "C", "A", "B", "C")]
    assert (
        infer_dataset_ordering(grouped, "station", None)
        == DatasetOrdering.ENTITY_GROUPED
    )
    assert (
        infer_dataset_ordering(interleaved, "station", None)
        == DatasetOrdering.EFFECTIVELY_RANDOM
    )


def test_retrieval_plan_accounts_for_dimensions_and_cap() -> None:
    rows = [
        {"station": station, "pollutant": pollutant, "surface": surface}
        for station in ("A", "B")
        for pollutant in ("pm25", "pm10", "ozone")
        for surface in ("road", "background")
    ]
    population, plan = build_retrieval_plan(
        rows,
        entity_field="station",
        timestamp_field=None,
        metric_dimension_fields=("pollutant",),
        observation_dimension_fields=("surface",),
        target_observations_per_entity=10,
        max_import_rows=100,
    )
    assert population.estimated_entities == 2
    assert plan.dimension_multiplier == 6
    assert plan.target_rows == 100
    assert plan.observations_per_entity == 50


def test_missing_entity_field_produces_single_logical_stream_plan() -> None:
    population, plan = build_retrieval_plan(
        [{"value": 1}, {"value": 2}],
        entity_field=None,
        timestamp_field=None,
    )
    assert population.estimated_entities == 0
    assert plan.estimated_entities == 1
    assert plan.target_rows == 50
