"""Regression coverage for authoritative CKAN CSV resources."""

from __future__ import annotations

import asyncio
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


_ROOT = Path(__file__).parents[1] / "custom_components" / "open_data"
package = ModuleType("custom_components.open_data")
package.__path__ = [str(_ROOT)]
providers_package = ModuleType("custom_components.open_data.providers")
providers_package.__path__ = [str(_ROOT / "providers")]
sys.modules.setdefault("custom_components", ModuleType("custom_components"))
sys.modules["custom_components.open_data"] = package
sys.modules["custom_components.open_data.providers"] = providers_package


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
ckan = _load(
    "custom_components.open_data.providers.ckan", _ROOT / "providers" / "ckan.py"
)


def _csv(resource_id: str = "csv-current") -> dict:
    return {
        "id": resource_id,
        "format": "CSV",
        "url": "https://files.example/current.csv",
        "state": "active",
        "datastore_active": False,
    }


def test_csv_is_preferred_over_a_stale_datastore_mirror() -> None:
    package_data = {
        "resources": [
            {
                "id": "stale-mirror",
                "format": "API",
                "datastore_active": True,
                "state": "active",
            },
            _csv(),
        ]
    }

    assert ckan.CkanProvider._select_resource(package_data, None)["id"] == "csv-current"


def test_newest_active_csv_is_selected_when_package_has_multiple_files() -> None:
    older = {**_csv("archive"), "last_modified": "2025-01-01T00:00:00"}
    current = {**_csv("current"), "last_modified": "2026-07-21T00:00:00"}

    selected = ckan.CkanProvider._select_resource(
        {"resources": [older, current]}, None
    )

    assert selected["id"] == "current"


def test_catalog_keeps_csv_only_packages_and_exposes_resource_id() -> None:
    datasets = ckan.CkanProvider._normalize_packages(
        [
            {
                "name": "weather",
                "title": "Weather",
                "resources": [_csv("weather-csv")],
            },
            {
                "name": "pdf-only",
                "title": "Report",
                "resources": [{"id": "report", "format": "PDF"}],
            },
        ]
    )

    assert [(item.dataset_id, item.resource_id) for item in datasets] == [
        ("weather", "weather-csv")
    ]


class _CsvProvider(ckan.CkanProvider):
    def __init__(self, rows: list[dict[str, str]]) -> None:
        super().__init__(None, "https://data.example")
        self.rows = rows
        self.actions: list[str] = []

    async def _action(self, action: str, params: dict[str, str]):
        self.actions.append(action)
        if action == "package_show":
            return {
                "name": "air-quality",
                "title": "Air quality",
                "resources": [_csv()],
            }
        raise AssertionError(f"CSV resource unexpectedly used {action}")

    async def async_iter_csv_rows(self, url: str):
        assert url.endswith("current.csv")
        for row in self.rows:
            yield row


def test_csv_schema_and_latest_rows_do_not_query_datastore() -> None:
    provider = _CsvProvider(
        [
            {"station": "A", "observed_at": "2026-07-20", "pm2_5": "5"},
            {"station": "B", "observed_at": "2026-07-21", "pm2_5": "8"},
            {"station": "A", "observed_at": "2026-07-22", "pm2_5": "7"},
        ]
    )

    dataset = asyncio.run(provider.async_get_dataset("air-quality"))
    latest = asyncio.run(
        provider.async_observation_rows(
            "air-quality",
            dataset.resource_id,
            "observed_at",
            {"station": "A"},
            limit=1,
        )
    )

    assert [field.name for field in dataset.fields] == [
        "station",
        "observed_at",
        "pm2_5",
    ]
    assert latest == [
        {"station": "A", "observed_at": "2026-07-22", "pm2_5": "7"}
    ]
    assert set(provider.actions) == {"package_show"}


def test_full_csv_is_reused_for_multiple_record_filters() -> None:
    provider = _CsvProvider(
        [
            {"station": "A", "observed_at": "2026-07-21", "pm2_5": "7"},
            {"station": "B", "observed_at": "2026-07-21", "pm2_5": "8"},
        ]
    )
    downloads = 0
    original = provider.async_iter_csv_rows

    async def counted(url: str):
        nonlocal downloads
        downloads += 1
        async for row in original(url):
            yield row

    provider.async_iter_csv_rows = counted
    asyncio.run(provider.async_get_dataset("air-quality"))
    asyncio.run(provider.async_observation_rows("air-quality", None, "observed_at", {"station": "A"}))
    asyncio.run(provider.async_observation_rows("air-quality", None, "observed_at", {"station": "B"}))

    # One bounded schema sample, then one complete cached preparation pass.
    assert downloads == 2
