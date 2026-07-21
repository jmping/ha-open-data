"""Regression tests for ArcGIS Hub provider normalization."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"

package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
providers = ModuleType("custom_components.open_data.providers")
providers.__path__ = [str(_ROOT / "providers")]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package
sys.modules["custom_components.open_data.providers"] = providers


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("custom_components.open_data.models", _ROOT / "models.py")
_load("custom_components.open_data.providers.base", _ROOT / "providers" / "base.py")
_load("custom_components.open_data.providers.common", _ROOT / "providers" / "common.py")
arcgis = _load(
    "custom_components.open_data.providers.arcgis_hub",
    _ROOT / "providers" / "arcgis_hub.py",
)


def test_dcat_item_keeps_queryable_feature_service() -> None:
    item = {
        "identifier": "https://hub.arcgis.com/datasets/abc123",
        "title": "Air Quality Monitoring Sites",
        "description": "Current monitoring locations",
        "distribution": [
            {"downloadURL": "https://example.org/data.csv"},
            {
                "accessURL": (
                    "https://services.arcgis.com/example/arcgis/rest/services/"
                    "Air_Quality/FeatureServer/0"
                )
            },
        ],
    }

    dataset = arcgis.ArcGisHubProvider._normalize_item(item)

    assert dataset is not None
    assert dataset.dataset_id == "abc123"
    assert dataset.resource_id.endswith("/FeatureServer/0")


def test_dcat_item_without_feature_service_is_not_importable() -> None:
    item = {
        "identifier": "download-only",
        "title": "PDF report",
        "distribution": [{"downloadURL": "https://example.org/report.pdf"}],
    }

    assert arcgis.ArcGisHubProvider._normalize_item(item) is None


def test_arcgis_field_names_are_validated() -> None:
    assert arcgis.ArcGisHubProvider._field("station_id") == "station_id"

    try:
        arcgis.ArcGisHubProvider._field("station id; DROP TABLE")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe ArcGIS field name was accepted")
