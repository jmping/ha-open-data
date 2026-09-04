"""Regression tests for opt-in GitHub failure reports."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "open_data"
    / "failure_reporting.py"
)
spec = spec_from_file_location("failure_reporting", _PATH)
assert spec is not None and spec.loader is not None
module = module_from_spec(spec)
spec.loader.exec_module(module)


def test_failure_report_excludes_raw_values_and_secrets() -> None:
    report = module.build_failure_report(
        {
            "provider": "ckan",
            "portal_url": "https://example.test/data",
            "dataset_id": "weather",
            "stage": "temporal",
            "error_type": "ValueError",
            "error_message": "timestamp inference failed",
            "metric_fields": ["temperature", "humidity"],
            "timestamp_fields": ["year", "month", "day"],
            "raw_rows": [{"temperature": 71.2}],
            "token": "secret-token",
            "authorization": "Bearer secret",
        }
    )

    serialized = report["body"]
    assert "weather" in serialized
    assert "temperature" in serialized
    assert "71.2" not in serialized
    assert "secret-token" not in serialized
    assert "Bearer secret" not in serialized
    assert "issues/new" in report["issue_url"]


def test_failure_fingerprint_ignores_city_specific_identifiers() -> None:
    first = module.failure_fingerprint(
        {
            "provider": "socrata",
            "portal_url": "https://city-a.example",
            "dataset_id": "a1",
            "stage": "sample",
            "error_type": "ValueError",
            "metric_fields": ["temperature"],
        }
    )
    second = module.failure_fingerprint(
        {
            "provider": "socrata",
            "portal_url": "https://city-b.example",
            "dataset_id": "b2",
            "stage": "sample",
            "error_type": "ValueError",
            "metric_fields": ["temperature"],
        }
    )
    assert first == second
