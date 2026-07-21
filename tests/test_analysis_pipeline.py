"""Tests for the two-pass history-aware analysis pipeline."""

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
        self.observation_request = None

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
        self.observation_request = (entity_field, timestamp_field)
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


def test_pipeline_uses_first_pass_candidates_for_historical_sampling() -> None:
    import asyncio

    dataset = OpenDataDataset(
        dataset_id="pfas",
        title="PFAS Samples",
        fields=(
            OpenDataField("site_id", "Site"),
            OpenDataField("sample_date", "Sample Date"),
            OpenDataField("analyte", "Analyte"),
            OpenDataField("result", "Result"),
        ),
    )
    provider = FakeProvider()

    result = asyncio.run(pipeline.async_analyze_dataset(provider, dataset))

    assert provider.observation_request == ("site_id", "sample_date")
    assert result.initial_row_count == 1
    assert result.historical_row_count == 8
    assert result.observations.shape.value == "long"
    assert result.observations.metric_dimension_fields == ("analyte",)
    assert result.observations.value_fields == ("result",)
