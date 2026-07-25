"""Home Assistant config-flow regressions for pre-setup registry state."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.open_data.const import DOMAIN
from custom_components.open_data.preparation import DATA_PREPARATIONS


async def test_portal_flow_initializes_registry_before_integration_setup(hass) -> None:
    """Submitting a portal must not require hass.data[DOMAIN] to exist."""
    hass.data.pop(DOMAIN, None)

    prepare_task = hass.async_create_task(_never_finishes())
    registry = AsyncMock()
    registry.get.return_value = None
    registry.start.return_value = prepare_task

    with (
        patch(
            "custom_components.open_data.config_flow.PreparationRegistry",
            return_value=registry,
        ),
        patch(
            "custom_components.open_data.config_flow.async_resolve_reference",
            side_effect=lambda _session, reference: _return(reference),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "source_location": "https://ckan.a2gov.org",
                "portal_url": "",
            },
        )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert DOMAIN in hass.data
    assert hass.data[DOMAIN][DATA_PREPARATIONS] is registry
    registry.async_load.assert_awaited_once()
    registry.start.assert_called_once()
    prepare_task.cancel()


async def _never_finishes() -> None:
    """Keep the mocked preparation task pending long enough to show progress."""
    import asyncio

    await asyncio.Event().wait()


async def _return(value):
    return value
