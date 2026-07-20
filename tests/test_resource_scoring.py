"""Tests for deterministic CKAN resource scoring."""

from custom_components.open_data.providers.resource_scoring import (
    choose_best_resource,
    score_resource,
)


def test_score_prefers_datastore_active_resource() -> None:
    """DataStore support should dominate weaker metadata signals."""
    active = score_resource(
        {
            "datastore_active": True,
            "state": "active",
            "format": "CSV",
        }
    )
    inactive = score_resource(
        {
            "datastore_active": False,
            "state": "active",
            "format": "CSV",
        }
    )

    assert active.score > inactive.score
    assert "DataStore enabled" in active.reasons


def test_choose_best_resource_prefers_supported_format() -> None:
    """A recognized structured format should break otherwise equal scores."""
    resources = [
        {
            "id": "unknown-format",
            "datastore_active": True,
            "state": "active",
            "format": "BIN",
        },
        {
            "id": "csv",
            "datastore_active": True,
            "state": "active",
            "format": "CSV",
        },
    ]

    assert choose_best_resource(resources) == resources[1]


def test_choose_best_resource_uses_modification_time_as_tie_breaker() -> None:
    """The newest equally suitable resource should be selected."""
    resources = [
        {
            "id": "older",
            "datastore_active": True,
            "state": "active",
            "format": "CSV",
            "last_modified": "2025-01-01T00:00:00Z",
        },
        {
            "id": "newer",
            "datastore_active": True,
            "state": "active",
            "format": "CSV",
            "last_modified": "2025-02-01T00:00:00Z",
        },
    ]

    assert choose_best_resource(resources) == resources[1]


def test_choose_best_resource_preserves_order_for_complete_tie() -> None:
    """Input order should remain the final deterministic tie-breaker."""
    resources = [
        {
            "id": "first",
            "datastore_active": True,
            "state": "active",
        },
        {
            "id": "second",
            "datastore_active": True,
            "state": "active",
        },
    ]

    assert choose_best_resource(resources) == resources[0]


def test_choose_best_resource_ignores_ineligible_resources() -> None:
    """Inactive or non-DataStore resources must not be selected."""
    resources = [
        {
            "id": "inactive",
            "datastore_active": True,
            "state": "deleted",
            "format": "CSV",
        },
        {
            "id": "not-datastore",
            "datastore_active": False,
            "state": "active",
            "format": "CSV",
        },
    ]

    assert choose_best_resource(resources) is None


def test_invalid_modification_timestamp_is_ignored() -> None:
    """Malformed provider metadata should not prevent resource selection."""
    resource = {
        "id": "resource",
        "datastore_active": True,
        "state": "active",
        "last_modified": "not-a-date",
    }

    result = score_resource(resource)

    assert result.modified is None
    assert choose_best_resource([resource]) == resource
