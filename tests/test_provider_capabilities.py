"""Contract tests for provider capability declarations."""

import ast
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


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
base = _load(
    "custom_components.open_data.providers.base", _ROOT / "providers" / "base.py"
)


def _declared_capabilities(path: Path) -> dict[str, bool]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "capabilities"
            for target in node.targets
        ):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        return {
            keyword.arg: bool(ast.literal_eval(keyword.value))
            for keyword in call.keywords
            if keyword.arg is not None
        }
    raise AssertionError(f"No capability declaration found in {path}")


def test_extended_capabilities_derive_from_declared_operations() -> None:
    capabilities = base.ProviderCapabilities(
        supports_schema=True,
        supports_latest_row=True,
        supports_timeseries=True,
        supports_station_filtering=True,
        supports_streaming=True,
    )

    assert capabilities.supports_selected_history is True
    assert capabilities.supports_source_modified_time is True
    assert capabilities.supports_ordering is True
    assert capabilities.supports_downloadable_resources is True
    assert all(isinstance(value, bool) for value in capabilities.as_dict().values())


def test_extended_capability_defaults_can_be_overridden() -> None:
    capabilities = base.ProviderCapabilities(
        supports_schema=True,
        supports_source_modified_time=False,
        supports_streaming=False,
        supports_downloadable_resources=True,
    )

    assert capabilities.supports_source_modified_time is False
    assert capabilities.supports_downloadable_resources is True


def test_unsupported_capability_has_structured_failure() -> None:
    class Provider:
        provider_name = "Fixture"
        capabilities = base.ProviderCapabilities()
        require_capability = base.OpenDataProvider.require_capability

    with pytest.raises(
        base.OpenDataUnsupportedCapabilityError,
        match="Fixture does not support selected history",
    ):
        Provider().require_capability("supports_selected_history")


def test_unknown_capability_is_a_programming_error() -> None:
    class Provider:
        provider_name = "Fixture"
        capabilities = base.ProviderCapabilities()
        require_capability = base.OpenDataProvider.require_capability

    with pytest.raises(ValueError, match="Unknown provider capability"):
        Provider().require_capability("supports_magic")


@pytest.mark.parametrize(
    "filename",
    ("ckan.py", "socrata.py", "arcgis_hub.py", "opendatasoft.py"),
)
def test_every_provider_family_declares_the_runtime_contract(filename: str) -> None:
    declared = _declared_capabilities(_ROOT / "providers" / filename)
    required = {
        "supports_search",
        "supports_catalog_paging",
        "supports_schema",
        "supports_latest_row",
        "supports_timeseries",
        "supports_station_filtering",
        "supports_sample_rows",
        "supports_distinct_values",
    }
    assert required <= declared.keys()
    assert all(isinstance(declared[name], bool) for name in required)


def test_provider_contract_defaults_are_conservative() -> None:
    capabilities = base.ProviderCapabilities()
    assert not any(capabilities.as_dict().values())
