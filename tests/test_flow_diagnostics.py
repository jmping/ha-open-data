"""Tests for config-flow diagnostic logging."""

from __future__ import annotations

import logging

from custom_components.open_data import flow_diagnostics


def test_safe_value_redacts_secrets_and_bounds_values() -> None:
    value = flow_diagnostics._safe_value(
        {
            "source_location": "https://data.example.gov/" + "x" * 600,
            "api_key": "super-secret",
            "nested": {"token": "another-secret"},
            "items": list(range(30)),
        }
    )

    assert value["api_key"] == "<redacted>"
    assert value["nested"]["token"] == "<redacted>"
    assert len(value["source_location"]) == 500
    assert value["items"] == list(range(20))


def test_serious_diagnostic_log_contains_context_and_traceback(caplog) -> None:
    try:
        raise RuntimeError("catalog exploded")
    except RuntimeError as exc:
        with caplog.at_level(logging.ERROR, logger="custom_components.open_data"):
            flow_diagnostics.log_flow_exception(
                "prepare_catalog",
                exc,
                integration_version="0.1.2",
                portal_url="https://data.example.gov",
                provider="ckan",
                password="do-not-log",
            )

    message = caplog.text
    assert "Open Data config flow failed" in message
    assert "flow_step=prepare_catalog" in message
    assert "integration_version=0.1.2" in message
    assert "portal_url" in message
    assert "https://data.example.gov" in message
    assert "<redacted>" in message
    assert "do-not-log" not in message
    assert "RuntimeError: catalog exploded" in message
