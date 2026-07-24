"""Regression tests for unified source-location routing."""

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package

const = ModuleType("custom_components.open_data.const")
const.PROVIDER_CKAN = "ckan"
const.PROVIDER_SOCRATA = "socrata"
sys.modules["custom_components.open_data.const"] = const

spec = spec_from_file_location(
    "custom_components.open_data.reference", _ROOT / "reference.py"
)
assert spec is not None and spec.loader is not None
reference = module_from_spec(spec)
sys.modules[spec.name] = reference
spec.loader.exec_module(reference)


def test_ckan_dataset_page_routes_directly() -> None:
    parsed = reference.parse_reference(
        "https://data.example.test/dataset/air-quality"
    )
    assert parsed.dataset_id == "air-quality"
    assert parsed.is_portal is False


def test_ckan_portal_root_routes_to_catalog() -> None:
    parsed = reference.parse_reference("https://data.example.test/")
    assert parsed.dataset_id is None
    assert parsed.is_portal is True


def test_socrata_dataset_page_routes_directly() -> None:
    parsed = reference.parse_reference(
        "https://data.example.test/resource/abcd-1234.json"
    )
    assert parsed.dataset_id == "abcd-1234"
    assert parsed.is_portal is False


def test_socrata_catalog_routes_to_catalog() -> None:
    parsed = reference.parse_reference(
        "https://data.example.test/api/catalog/v1"
    )
    assert parsed.dataset_id is None
    assert parsed.is_portal is True
