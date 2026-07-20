"""Data update coordinator for Socrata datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SocrataClient, SocrataDatasetMetadata, SocrataError
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
        self.metadata: SocrataDatasetMetadata | None = None

    async def _async_update_data(self) -> SocrataCoordinatorData:
        """Fetch metadata once and then fetch the newest source row."""
        try:
            if self.metadata is None:
                self.metadata = await self.client.async_get_dataset_metadata(
                    self.dataset_id
                )
            row = await self.client.async_latest_row(
                self.dataset_id, self.timestamp_field
            )
        except SocrataError as err:
            raise UpdateFailed(str(err)) from err

        return SocrataCoordinatorData(row=row, retrieved_at=datetime.now(UTC))
