"""Tests for deterministic CKAN resource scoring."""

from datetime import UTC

from custom_components.open_data.providers.resource_scoring import (
    choose_best_resource,
    score_resource,
)


def test_score_prefers_datastore_active_resource() -> None:
    active = score_resource({"datastore_active": True, "state": "active", "format": "CSV"})
    inactive = score_resource({"datastore_active": False, "state": "active", "format": "CSV"})
    assert active.score > inactive.score
    assert "DataStore enabled" in active.reasons


def test_choose_best_resource_prefers_supported_format() -> None:
    resources = [
        {"id": "unknown-format", "datastore_active": True, "state": "active", "format": "BIN"},
        {"id": "csv", "datastore_active": True, "state": "active", "format": "CSV"},
    ]
    assert choose_best_resource(resources) == resources[1]


def test_choose_best_resource_accepts_mime_formats() -> None:
    resources = [
        {"id": "api", "datastore_active": True, "state": "active", "format": "API"},
        {"id": "csv", "datastore_active": True, "state": "active", "format": "text/csv"},
    ]
    assert choose_best_resource(resources) == resources[1]


def test_choose_best_resource_uses_modification_time_as_tie_breaker() -> None:
    resources = [
        {"id": "older", "datastore_active": True, "state": "active", "format": "CSV", "last_modified": "2025-01-01T00:00:00Z"},
        {"id": "newer", "datastore_active": True, "state": "active", "format": "CSV", "last_modified": "2025-02-01T00:00:00Z"},
    ]
    assert choose_best_resource(resources) == resources[1]


def test_choose_best_resource_preserves_order_for_complete_tie() -> None:
    resources = [
        {"id": "first", "datastore_active": True, "state": "active"},
        {"id": "second", "datastore_active": True, "state": "active"},
    ]
    assert choose_best_resource(resources) == resources[0]


def test_choose_best_resource_ignores_ineligible_resources() -> None:
    resources = [
        {"id": "inactive", "datastore_active": True, "state": "deleted", "format": "CSV"},
        {"id": "not-datastore", "datastore_active": False, "state": "active", "format": "CSV"},
    ]
    assert choose_best_resource(resources) is None


def test_invalid_primary_timestamp_falls_back_to_metadata_timestamp() -> None:
    result = score_resource(
        {
            "datastore_active": True,
            "last_modified": "not-a-date",
            "metadata_modified": "2025-03-01T12:30:00Z",
        }
    )
    assert result.modified is not None
    assert result.modified.tzinfo is UTC
    assert result.modified.isoformat() == "2025-03-01T12:30:00+00:00"


def test_naive_timestamp_is_normalized_to_utc() -> None:
    result = score_resource(
        {"datastore_active": True, "last_modified": "2025-03-01T12:30:00"}
    )
    assert result.modified is not None
    assert result.modified.tzinfo is UTC


def test_none_state_uses_default_active_state() -> None:
    resource = {"id": "resource", "datastore_active": True, "state": None}
    assert choose_best_resource([resource]) == resource
