"""Home Assistant config-flow regressions for pre-setup registry state."""

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.open_data.const import DOMAIN, PROVIDER_CKAN
from custom_components.open_data.discovery import score_dataset
from custom_components.open_data.models import OpenDataDataset
from custom_components.open_data.preparation import DATA_PREPARATIONS


class _Prepared:
    status = "ready"
    portal_url = "https://ckan.a2gov.org"
    provider = PROVIDER_CKAN
    candidates = (
        score_dataset(
            OpenDataDataset(
                dataset_id="weather-stations",
                title="Weather Stations",
            )
        ),
    )


class _FakePreparationRegistry:
    """Faithful test double for the registry's sync/async surface."""

    def __init__(self, prepare_task=None, prepared=None) -> None:
        self.async_load = AsyncMock()
        self.get = Mock(return_value=prepared)
        self.start = Mock(return_value=prepare_task)


async def _start_known_source_flow(hass, source_location: str):
    """Start the user menu, choose known source, and submit one source URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "known"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "known"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "source_location": source_location,
            "portal_url": "",
        },
    )


async def test_portal_flow_initializes_registry_before_integration_setup(hass) -> None:
    """Submitting a portal must not require hass.data[DOMAIN] to exist."""
    hass.data.pop(DOMAIN, None)

    prepare_task = hass.async_create_task(_never_finishes())
    registry = _FakePreparationRegistry(prepare_task=prepare_task)

    async def _resolve(_session, reference):
        return reference

    try:
        with (
            patch(
                "custom_components.open_data.config_flow.PreparationRegistry",
                return_value=registry,
            ),
            patch(
                "custom_components.open_data.config_flow.async_resolve_reference",
                side_effect=_resolve,
            ),
        ):
            result = await _start_known_source_flow(
                hass, "https://ckan.a2gov.org"
            )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN][DATA_PREPARATIONS] is registry
        registry.async_load.assert_awaited_once()
        registry.start.assert_called_once()
    finally:
        prepare_task.cancel()
        with suppress(asyncio.CancelledError):
            await prepare_task


async def test_prepared_ann_arbor_portal_reaches_dataset_picker(hass) -> None:
    """A prepared Ann Arbor portal must render the picker with optional metadata absent."""
    registry = _FakePreparationRegistry(prepared=_Prepared())
    hass.data[DOMAIN] = {DATA_PREPARATIONS: registry}

    async def _resolve(_session, reference):
        return reference

    with patch(
        "custom_components.open_data.config_flow.async_resolve_reference",
        side_effect=_resolve,
    ):
        result = await _start_known_source_flow(hass, "data.a2gov.org")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discover"
    schema = result["data_schema"].schema
    selector = next(iter(schema.values()))
    options = selector.config["options"]
    assert options[0]["value"] == "weather-stations"
    assert options[0]["label"] == "Weather Stations · weather"


async def _never_finishes() -> None:
    """Keep the mocked preparation task pending long enough to show progress."""
    await asyncio.Event().wait()
