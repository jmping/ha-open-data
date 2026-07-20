"""Data update coordinator for Socrata datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SocrataClient, SocrataError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SocrataCoordinatorData:
    """Latest dataset row plus retrieval metadata."""

    row: dict[str, Any] | None
    retrieved_at: datetime


class SocrataDataUpdateCoordinator(DataUpdateCoordinator[SocrataCoordinatorData]):
    """Coordinate updates for one Socrata dataset."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SocrataClient,
        dataset_id: str,
        timestamp_field: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}:{dataset_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.dataset_id = dataset_id
        self.timestamp_field = timestamp_field

    async def _async_update_data(self) -> SocrataCoordinatorData:
        """Fetch the newest source row."""
        try:
            row = await self.client.async_latest_row(
                self.dataset_id, self.timestamp_field
            )
        except SocrataError as err:
            raise UpdateFailed(str(err)) from err

        return SocrataCoordinatorData(row=row, retrieved_at=datetime.now(UTC))
