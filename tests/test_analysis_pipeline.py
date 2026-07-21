"""Tests for the adaptive history-aware analysis pipeline."""

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
            (entity_field, timestamp_field, entity_limit * observations_per_entity)
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
        self.observation_requests.append((entity_field, timestamp_field, requested))
        analyte_count = 2 if requested <= 200 else 12 if requested <= 1000 else 14
        rows = []
        for index in range(requested):
            rows.append(
                {
                    "site_id": f"S{index % 20}",
                    "sample_date": f"2026-01-{(index % 28) + 1:02d}",
                    "analyte": f"A{index % analyte_count}",
                    "result": float(index),
                }
            )
        return rows


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


def test_pipeline_uses_first_pass_candidates_for_historical_sampling() -> None:
    import asyncio

    provider = FakeProvider()
    result = asyncio.run(pipeline.async_analyze_dataset(provider, _dataset()))

    assert provider.observation_requests[0][:2] == ("site_id", "sample_date")
    assert provider.observation_requests[0][2] >= 200
    assert result.initial_row_count == 1
    assert result.historical_row_count == 7
    assert result.observations.shape.value == "long"
    assert result.observations.metric_dimension_fields == ("analyte",)
    assert result.observations.value_fields == ("result",)
    assert result.sampling.converged is True
    assert result.sampling.stopped_reason == "provider_exhausted"


def test_pipeline_escalates_to_deep_sample_when_metric_granularity_expands() -> None:
    import asyncio

    provider = ExpandingProvider()
    result = asyncio.run(pipeline.async_analyze_dataset(provider, _dataset()))

    requested = [item[2] for item in provider.observation_requests]
    assert requested == [200, 1000, 20000]
    assert len(result.sampling.stages) == 3
    assert result.sampling.stages[1].metric_value_count > result.sampling.stages[0].metric_value_count
    assert result.sampling.requested_row_cap == 20000
    assert result.sampling.retrieved_row_count >= 20000
