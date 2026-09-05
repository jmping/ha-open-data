"""Intent-first options menu for already imported Open Data entries."""

from __future__ import annotations

from typing import Any

from homeassistant.data_entry_flow import FlowResult

from .options_flow import OpenDataOptionsFlow


class OpenDataOptionsMenuFlow(OpenDataOptionsFlow):
    """Let users improve an import later without walking a mandatory wizard."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Offer independent post-import adjustments."""
        return self.async_show_menu(
            step_id="menu",
            menu_options=["records", "semantics", "temporal", "advanced"],
        )

    async def async_step_records(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Adjust records and measures without forcing the rest of advanced review."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self._config_entry.options,
                    **self._structure_options,
                    **dict(user_input),
                },
            )
        return await super().async_step_records(None)

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter the full structural review only when explicitly requested."""
        return await super().async_step_init(user_input)
