"""Tests for adaptive analysis, entity estimation, and retrieval planning."""

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
_load("analyzer")
_load("observation_model")
base = _load("providers.base")
pipeline = _load("analysis_pipeline")
OpenDataDataset = models.OpenDataDataset
OpenDataField = models.OpenDataField


class FakeProvider(base.OpenDataProvider):
    provider_name = "Fake"
    portal_url = "https://example.test"

    def __init__(self) -> None:
        self.observation_requests = []

    async def async_verify_portal(self) -> None:
        return None

    async def async_get_dataset(self, dataset_id, resource_id=None):
        raise NotImplementedError

    async def async_latest_row(
        self, dataset_id, resource_id=None, timestamp_field=None, filters=None
    ):
        raise NotImplementedError

    async def async_sample_rows(self, dataset_id, resource_id=None, *, limit=50):
        return [
            {
                "site_id": "A",
                "sample_date": "2026-01-01",
                "analyte": "PFOS",
                "result": 4.2,
            }
        ]

    async def async_sample_observations(
        self,
        dataset_id,
        resource_id=None,
        *,
        entity_field=None,
        timestamp_field=None,
        entity_limit=20,
        observations_per_entity=25,
    ):
        self.observation_requests.append(
            (entity_field, timestamp_field, entity_limit, observations_per_entity)
        )
        return [
            {
                "site_id": site,
                "sample_date": date,
                "analyte": analyte,
                "result": value,
            }
            for site in ("A", "B")
            for date in ("2025-01-01", "2026-01-01")
            for analyte, value in (("PFOS", 4.2), ("PFOA", 1.8))
        ]


class ExpandingProvider(FakeProvider):
    """Return increasing lower-level metric diversity at each requested stage."""

    async def async_sample_observations(
        self,
        dataset_id,
        resource_id=None,
        *,
        entity_field=None,
        timestamp_field=None,
        entity_limit=20,
        observations_per_entity=25,
    ):
        requested = entity_limit * observations_per_entity
        self.observation_requests.append(
            (entity_field, timestamp_field, entity_limit, observations_per_entity)
        )
        analyte_count = 2 if requested <= 200 else 12 if requested <= 1000 else 14
        return [
            {
                "site_id": f"S{index % 20}",
                "sample_date": f"2026-01-{(index % 28) + 1:02d}",
                "analyte": f"A{index % analyte_count}",
                "result": float(index),
            }
            for index in range(requested)
        ]


def _dataset() -> OpenDataDataset:
    return OpenDataDataset(
        dataset_id="pfas",
        title="PFAS Samples",
        fields=(
            OpenDataField("site_id", "Site"),
            OpenDataField("sample_date", "Sample Date"),
            OpenDataField("analyte", "Analyte"),
            OpenDataField("result", "Result"),
        ),
    )


def test_random_sample_with_repeated_entities_estimates_near_observed() -> None:
    rows = [
        {"station": f"S{index % 73}"}
        for index in range(1000)
    ]

    estimate = pipeline.estimate_entity_population(rows, "station")

    assert estimate.observed_entities == 73
    assert estimate.estimated_entities == 73
    assert estimate.singletons == 0
    assert estimate.confidence == 1.0


def test_singleton_tail_increases_population_estimate() -> None:
    rows = []
    rows.extend({"station": f"common-{index % 20}"} for index in range(200))
    rows.extend({"station": f"rare-{index}"} for index in range(10))

    estimate = pipeline.estimate_entity_population(rows, "station")

    assert estimate.observed_entities == 30
    assert estimate.singletons == 10
    assert estimate.estimated_entities > estimate.observed_entities


def test_retrieval_plan_scales_by_entities_and_dimensions() -> None:
    dataset = _dataset()
    rows = [
        {
            "site_id": f"S{index % 10}",
            "sample_date": f"2026-01-{(index % 28) + 1:02d}",
            "analyte": f"A{index % 4}",
            "result": float(index),
        }
        for index in range(400)
    ]
    model = pipeline.analyze_observations(dataset, rows)

    population, plan = pipeline.build_retrieval_plan(
        model, rows, target_observations_per_entity=25
    )

    assert population.estimated_entities == 10
    assert plan.dimension_multiplier == 4
    assert plan.target_rows == 1000
    assert plan.entity_limit == 10
    assert plan.observations_per_entity == 100


def test_pipeline_uses_estimated_population_for_final_retrieval() -> None:
    import asyncio

    provider = FakeProvider()
    result = asyncio.run(pipeline.async_analyze_dataset(provider, _dataset()))

    assert provider.observation_requests[0][:2] == ("site_id", "sample_date")
    final_request = provider.observation_requests[-1]
    assert final_request[2] == result.sampling.entity_population.estimated_entities
    assert final_request[3] == result.sampling.retrieval_plan.observations_per_entity
    assert result.observations.shape.value == "long"
    assert result.sampling.stopped_reason == "provider_exhausted"
    assert result.sampling.imported_row_count == 8


def test_pipeline_escalates_when_metric_granularity_expands() -> None:
    import asyncio

    provider = ExpandingProvider()
    result = asyncio.run(
        pipeline.async_analyze_dataset(
            provider,
            _dataset(),
            max_import_rows=20000,
        )
    )

    analysis_requests = [entity_limit * per_entity for _, _, entity_limit, per_entity in provider.observation_requests[:-1]]
    assert analysis_requests == [200, 1000, 20000]
    assert len(result.sampling.stages) == 3
    assert result.sampling.stages[1].metric_value_count > result.sampling.stages[0].metric_value_count
    assert result.sampling.retrieval_plan.target_rows <= 20000
