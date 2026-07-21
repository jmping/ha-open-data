"""Home Assistant service API for Open Data discovery and diagnostics."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DATASET_ID,
    CONF_PORTAL_URL,
    CONF_RESOURCE_ID,
    DOMAIN,
)
from .feedback import FeedbackRegistry
from .portal_inspector import async_discover_catalog, async_inspect_portal

SERVICE_INSPECT_PORTAL = "inspect_portal"
SERVICE_SCAN_PORTAL = "scan_portal"
SERVICE_SEARCH_DATASETS = "search_datasets"
SERVICE_INSPECT_DATASET = "inspect_dataset"
SERVICE_REFRESH_ENTRY = "refresh_entry"
SERVICE_FEEDBACK_PREVIEW = "feedback_preview"

CONF_LIMIT = "limit"
CONF_QUERY = "query"
CONF_ENTRY_ID = "entry_id"
CONF_PORTAL_ID = "portal_id"
CONF_METADATA = "metadata"

_PORTAL_SCHEMA = cv.string
_LIMIT_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=100))


def _dataset_dict(dataset: Any, *, include_raw: bool = False) -> dict[str, Any]:
    result = {
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "description": dataset.description,
        "resource_id": dataset.resource_id,
        "fields": [asdict(field) for field in dataset.fields],
    }
    if include_raw:
        result["raw"] = dataset.raw
    return result


def _review_gate(
    *, provider_verified: bool, dataset_count: int, errors: list[str]
) -> dict[str, Any]:
    """Return a conservative decision for future AI-review collection."""
    reasons: list[str] = []
    if not provider_verified:
        reasons.append("provider API signature was not verified")
    if dataset_count < 1:
        reasons.append("no catalog datasets were discovered")
    if errors:
        reasons.append("catalog scan produced errors")
    return {
        "eligible_for_ai_review": not reasons,
        "reasons": reasons,
        "policy": "verified public provider API plus non-empty clean catalog scan",
    }


async def async_register_services(hass: HomeAssistant, feedback: FeedbackRegistry) -> None:
    """Register the public Open Data service surface."""

    async def inspect(call: ServiceCall):
        return await async_inspect_portal(
            async_get_clientsession(hass), call.data[CONF_PORTAL_URL]
        )

    async def async_inspect_portal_service(call: ServiceCall) -> dict[str, Any]:
        inspected = await inspect(call)
        return inspected.description.as_dict()

    async def async_scan_portal(call: ServiceCall) -> dict[str, Any]:
        inspected = await inspect(call)
        datasets, errors = await async_discover_catalog(
            inspected, limit=call.data[CONF_LIMIT]
        )
        gate = _review_gate(
            provider_verified=True,
            dataset_count=len(datasets),
            errors=errors,
        )
        return {
            **inspected.description.as_dict(),
            "dataset_count": len(datasets),
            "datasets": [_dataset_dict(item) for item in datasets],
            "errors": errors,
            "review_gate": gate,
        }

    async def async_search_datasets(call: ServiceCall) -> dict[str, Any]:
        inspected = await inspect(call)
        datasets = await inspected.provider.async_search_datasets(
            call.data.get(CONF_QUERY, ""), limit=call.data[CONF_LIMIT]
        )
        return {
            **inspected.description.as_dict(),
            "datasets": [_dataset_dict(item) for item in datasets],
        }

    async def async_inspect_dataset(call: ServiceCall) -> dict[str, Any]:
        inspected = await inspect(call)
        dataset = await inspected.provider.async_get_dataset(
            call.data[CONF_DATASET_ID], call.data.get(CONF_RESOURCE_ID)
        )
        return {
            **inspected.description.as_dict(),
            "dataset": _dataset_dict(dataset, include_raw=True),
        }

    async def async_refresh_entry(call: ServiceCall) -> dict[str, Any]:
        entry = hass.config_entries.async_get_entry(call.data[CONF_ENTRY_ID])
        if entry is None or entry.domain != DOMAIN:
            raise ValueError("Open Data config entry was not found")
        if entry.state is not ConfigEntryState.LOADED:
            raise ValueError("Open Data config entry is not loaded")
        await entry.runtime_data.async_request_refresh()
        return {"entry_id": entry.entry_id, "refreshed": True}

    async def async_feedback_preview(call: ServiceCall) -> dict[str, Any]:
        report = feedback.build_report(call.data[CONF_PORTAL_ID], call.data[CONF_METADATA])
        return {
            "would_submit": report is not None,
            "report": report.to_dict() if report is not None else None,
        }

    portal_schema = vol.Schema({vol.Required(CONF_PORTAL_URL): _PORTAL_SCHEMA})

    hass.services.async_register(
        DOMAIN,
        SERVICE_INSPECT_PORTAL,
        async_inspect_portal_service,
        schema=portal_schema,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_PORTAL,
        async_scan_portal,
        schema=vol.Schema(
            {
                vol.Required(CONF_PORTAL_URL): _PORTAL_SCHEMA,
                vol.Optional(CONF_LIMIT, default=50): _LIMIT_SCHEMA,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_DATASETS,
        async_search_datasets,
        schema=vol.Schema(
            {
                vol.Required(CONF_PORTAL_URL): _PORTAL_SCHEMA,
                vol.Optional(CONF_QUERY, default=""): cv.string,
                vol.Optional(CONF_LIMIT, default=20): _LIMIT_SCHEMA,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_INSPECT_DATASET,
        async_inspect_dataset,
        schema=vol.Schema(
            {
                vol.Required(CONF_PORTAL_URL): _PORTAL_SCHEMA,
                vol.Required(CONF_DATASET_ID): cv.string,
                vol.Optional(CONF_RESOURCE_ID): cv.string,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_ENTRY,
        async_refresh_entry,
        schema=vol.Schema({vol.Required(CONF_ENTRY_ID): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FEEDBACK_PREVIEW,
        async_feedback_preview,
        schema=vol.Schema(
            {
                vol.Required(CONF_PORTAL_ID): cv.string,
                vol.Required(CONF_METADATA): dict,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )


def async_remove_services(hass: HomeAssistant) -> None:
    """Remove all Open Data services."""
    for service in (
        SERVICE_INSPECT_PORTAL,
        SERVICE_SCAN_PORTAL,
        SERVICE_SEARCH_DATASETS,
        SERVICE_INSPECT_DATASET,
        SERVICE_REFRESH_ENTRY,
        SERVICE_FEEDBACK_PREVIEW,
    ):
        hass.services.async_remove(DOMAIN, service)
