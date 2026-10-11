"""Home Assistant config-flow regressions for pre-setup registry state."""

import asyncio
from contextlib import suppress
from unittest.mock import AsyncMock, Mock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.open_data.config_flow import (
    OpenDataConfigFlow,
    _async_wait_for_background_preparation,
)
from custom_components.open_data.const import DOMAIN, PROVIDER_CKAN
from custom_components.open_data.options_dyads import OpenDataDyadOptionsFlow
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


async def test_dataset_selection_stages_before_activation(hass) -> None:
    """Selecting a discovered dataset must not create a config entry yet."""
    flow = OpenDataConfigFlow()
    flow.hass = hass
    flow._portal_url = "https://ckan.a2gov.org"
    flow._provider_name = PROVIDER_CKAN
    flow._set_candidates(_Prepared.candidates)
    prepared_entry = {
        "unique_id": "ckan:https://ckan.a2gov.org:weather-stations:",
        "title": "Weather Stations",
        "data": {"dataset_id": "weather-stations"},
    }

    inventory = Mock()
    inventory.async_save_prepared = AsyncMock()
    with (
        patch.object(
            flow,
            "_async_prepare_dataset_entry",
            AsyncMock(return_value=prepared_entry),
        ),
        patch.object(
            flow, "_async_get_dataset_inventory",
            AsyncMock(return_value=inventory),
        ),
    ):
        result = await flow.async_step_discover(
            {"dataset_ids": ["weather-stations"]}
        )
    inventory.async_save_prepared.assert_awaited_once_with(prepared_entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "activate"
    assert flow._pending_entries == [prepared_entry]
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_activation_creates_prepared_config_entry(hass) -> None:
    """Only the activation submission should cross into HA runtime state."""
    flow = OpenDataConfigFlow()
    flow.hass = hass
    flow._pending_entries = [
        {
            "unique_id": "ckan:https://ckan.a2gov.org:weather-stations:",
            "title": "Weather Stations",
            "data": {"dataset_id": "weather-stations"},
        }
    ]

    # In production the HA flow manager initializes mutable flow context.
    # Direct handler tests must supply it explicitly before setting unique_id.
    flow.context = {"source": config_entries.SOURCE_USER}
    inventory = Mock()
    inventory.async_mark_activated = AsyncMock()
    with patch.object(
        flow, "_async_get_dataset_inventory", AsyncMock(return_value=inventory)
    ):
        result = await flow.async_step_activate({})
    inventory.async_mark_activated.assert_awaited_once_with(
        flow._pending_entries[0]
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Weather Stations"
    assert result["data"] == {"dataset_id": "weather-stations"}


async def test_activation_without_prepared_dataset_aborts(hass) -> None:
    """A resumed or malformed flow cannot activate an absent dataset."""
    flow = OpenDataConfigFlow()
    flow.hass = hass

    result = await flow.async_step_activate()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_pending_datasets"


async def test_options_menu_has_resumable_menu_handler(hass) -> None:
    """The menu step advertised to HA must have a matching flow handler."""
    entry = Mock()
    entry.options = {}
    flow = OpenDataDyadOptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_init()
    resumed = await flow.async_step_menu()

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "menu"
    assert resumed["type"] is FlowResultType.MENU


async def test_local_source_file_is_loaded_off_the_event_loop(hass) -> None:
    """Packaged source profiles must not perform file I/O on HA's event loop."""
    flow = OpenDataConfigFlow()
    flow.hass = hass

    with patch(
        "custom_components.open_data.config_flow.rank_local_sources",
        return_value=[],
    ) as rank:
        result = await flow.async_step_local()

    assert result["type"] is FlowResultType.ABORT
    rank.assert_called_once_with(
        hass.config.latitude,
        hass.config.longitude,
        importable_only=True,
    )


async def test_leaving_flow_does_not_cancel_background_preparation(hass) -> None:
    """The registry-owned catalog job must outlive its config-flow observer."""
    preparation = hass.async_create_background_task(
        _never_finishes(),
        "Test Open Data preparation",
    )
    observer = hass.async_create_task(
        _async_wait_for_background_preparation(preparation),
        "Test Open Data preparation observer",
    )

    await asyncio.sleep(0)
    observer.cancel()
    with suppress(asyncio.CancelledError):
        await observer

    assert not preparation.cancelled()
    assert not preparation.done()

    preparation.cancel()
    with suppress(asyncio.CancelledError):
        await preparation


async def _never_finishes() -> None:
    """Keep the mocked preparation task pending long enough to show progress."""
    await asyncio.Event().wait()


async def test_prepared_inventory_can_be_resumed_without_discovery(hass) -> None:
    """Previously prepared datasets can be selected without rerunning a provider."""
    flow = OpenDataConfigFlow()
    flow.hass = hass
    prepared = {
        "unique_id": "ckan:https://ckan.a2gov.org:weather-stations:",
        "title": "Weather Stations",
        "data": {"dataset_id": "weather-stations"},
    }
    item = Mock(
        key="prepared-weather",
        title="Weather Stations",
        status="ready",
        dataset_id="weather-stations",
        resource_id=None,
        prepared=prepared,
    )
    inventory = Mock()
    inventory.datasets.return_value = (item,)
    with patch.object(
        flow, "_async_get_dataset_inventory", AsyncMock(return_value=inventory)
    ):
        listing = await flow.async_step_inventory()
        result = await flow.async_step_inventory({"inventory_dataset": item.key})
    assert listing["type"] is FlowResultType.FORM
    assert listing["step_id"] == "inventory"
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "activate"
    assert flow._pending_entries == [prepared]
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_prepared_inventory_absent_aborts(hass) -> None:
    flow = OpenDataConfigFlow()
    flow.hass = hass
    inventory = Mock()
    inventory.datasets.return_value = ()
    with patch.object(
        flow, "_async_get_dataset_inventory", AsyncMock(return_value=inventory)
    ):
        result = await flow.async_step_inventory()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_prepared_datasets"
