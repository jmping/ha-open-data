"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES, LOCATION_SAMPLE_LIMIT
from .locations import select_location_row
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataError, OpenDataProvider


class OpenDataCoordinator(DataUpdateCoordinator[OpenDataSnapshot]):
    """Coordinate metadata and latest-record updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: OpenDataProvider,
        dataset_id: str,
        resource_id: str | None,
        timestamp_field: str | None,
        location_field: str | None = None,
        location_value: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=f"Open Data {dataset_id}",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.provider = provider
        self.dataset_id = dataset_id
        self.resource_id = resource_id
        self.timestamp_field = timestamp_field
        self.location_field = location_field
        self.location_value = location_value
        self.dataset: OpenDataDataset | None = None

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            if self.dataset is None:
                self.dataset = await self.provider.async_get_dataset(
                    self.dataset_id, self.resource_id
                )
                self.resource_id = self.dataset.resource_id or self.resource_id
            rows = await self.provider.async_rows(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                limit=LOCATION_SAMPLE_LIMIT if self.location_value is not None else 1,
            )
            values = select_location_row(rows, self.location_field, self.location_value)
            return OpenDataSnapshot(dataset=self.dataset, values=values or {})
        except (OpenDataError, ValueError) as err:
            raise UpdateFailed(str(err)) from err
