"""Regression tests for modern ArcGIS Hub OGC Records catalogs."""

from importlib.util import module_from_spec, spec_from_file_location
import asyncio
from pathlib import Path
import sys
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
_PROVIDER_ROOT = _ROOT / "providers"

custom_components = sys.modules.setdefault("custom_components", ModuleType("custom_components"))
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules["custom_components.open_data"] = package
providers_package = ModuleType("custom_components.open_data.providers")
providers_package.__path__ = [str(_PROVIDER_ROOT)]
sys.modules["custom_components.open_data.providers"] = providers_package


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("custom_components.open_data.models", _ROOT / "models.py")
_load("custom_components.open_data.providers.base", _PROVIDER_ROOT / "base.py")
_load("custom_components.open_data.providers.common", _PROVIDER_ROOT / "common.py")
arcgis = _load(
    "custom_components.open_data.providers.arcgis_hub",
    _PROVIDER_ROOT / "arcgis_hub.py",
)


def test_ogc_record_normalizes_nested_feature_service() -> None:
    item = {
        "id": "abc123",
        "type": "dataset",
        "attributes": {
            "name": "Traffic Counts",
            "description": "Hourly count locations",
            "additionalResources": [
                {
                    "url": "https://services.arcgis.com/example/ArcGIS/rest/services/Traffic/FeatureServer/0"
                }
            ],
        },
    }

    dataset = arcgis.ArcGisHubProvider._normalize_item(item)

    assert dataset is not None
    assert dataset.dataset_id == "abc123"
    assert dataset.title == "Traffic Counts"
    assert dataset.resource_id.endswith("/FeatureServer/0")


def test_ogc_response_variants_are_supported() -> None:
    records = [{"id": "one"}, {"id": "two"}]

    assert arcgis.ArcGisHubProvider._ogc_records({"data": records}) == records
    assert arcgis.ArcGisHubProvider._ogc_records({"features": records}) == records
    assert arcgis.ArcGisHubProvider._ogc_records({"items": records}) == records


def test_nested_map_service_query_is_removed_from_resource_url() -> None:
    item = {
        "identifier": "roads",
        "title": "Road Network",
        "distribution": {
            "accessURL": "https://example.com/rest/services/Roads/MapServer?token=public"
        },
    }

    dataset = arcgis.ArcGisHubProvider._normalize_item(item)

    assert dataset is not None
    assert dataset.resource_id == "https://example.com/rest/services/Roads/MapServer"


def test_non_queryable_download_is_not_imported() -> None:
    item = {
        "id": "pdf-only",
        "attributes": {
            "name": "Annual Report",
            "downloadUrl": "https://example.com/report.pdf",
        },
    }

    assert arcgis.ArcGisHubProvider._normalize_item(item) is None


def test_catalog_item_is_compact_but_keeps_selection_metadata() -> None:
    item = {
        "id": "abc123",
        "attributes": {
            "name": "Weather Stations",
            "description": "Hourly readings",
            "tags": ["weather", "sensors"],
            "applicationProxies": [{"blob": "x" * 100_000}],
            "additionalResources": [
                {
                    "url": "https://services.arcgis.com/example/rest/services/Weather/FeatureServer/0"
                }
            ],
        },
    }

    dataset = arcgis.ArcGisHubProvider._normalize_item(item)

    assert dataset is not None
    assert dataset.raw["name"] == "Weather Stations"
    assert dataset.raw["tags"] == ["weather", "sensors"]
    assert "applicationProxies" not in dataset.raw
    assert len(str(dataset.raw)) < 5_000


def test_known_resource_does_not_reload_the_catalog() -> None:
    provider = object.__new__(arcgis.ArcGisHubProvider)

    async def fail_catalog(_dataset_id):
        raise AssertionError("selected ArcGIS resource reloaded the catalog")

    async def layer_metadata(_url, *, params=None):
        assert params == {"f": "json"}
        return {"fields": [{"name": "reading"}]}

    provider._catalog_item = fail_catalog
    provider._async_get_external_json = layer_metadata
    resource = "https://services.arcgis.com/example/rest/services/Weather/FeatureServer/0"

    assert asyncio.run(provider._layer_url("weather", resource)) == resource
