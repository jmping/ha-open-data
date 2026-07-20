"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL_MINUTES,
    LOCATION_SAMPLE_LIMIT,
    PROFILE_MAX_PAGES,
    PROFILE_PAGE_SIZE,
)
from .intelligence import DatasetIntelligence, DatasetProfile
from .locations import select_location_row
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataError, OpenDataProvider


class OpenDataCoordinator(DataUpdateCoordinator[OpenDataSnapshot]):
    """Coordinate metadata, profiling, and latest-record updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: OpenDataProvider,
        dataset_id: str,
        resource_id: str | None,
        timestamp_field: str | None,
        location_field: str | None = None,
        location_value: str | None = None,
        intelligence: DatasetIntelligence | None = None,
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
        self.intelligence = intelligence
        self.dataset: OpenDataDataset | None = None

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            if self.dataset is None:
                self.dataset = await self.provider.async_get_dataset(
                    self.dataset_id, self.resource_id
                )
                self.resource_id = self.dataset.resource_id or self.resource_id
            values = await self._async_latest_values()
            return OpenDataSnapshot(dataset=self.dataset, values=values or {})
        except (OpenDataError, ValueError) as err:
            raise UpdateFailed(str(err)) from err

    async def _async_latest_values(self) -> dict | None:
        """Return the newest matching row using learned paging strategy."""
        if self.location_value is None:
            rows = await self.provider.async_rows(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                limit=1,
            )
            return rows[0] if rows else None

        if self.timestamp_field:
            return await self._async_scan_pages(start_offset=0, forward=True)

        profile = self.intelligence.profile if self.intelligence else DatasetProfile()
        row_count = profile.row_count
        newest_region = profile.newest_region
        if newest_region == "end" and row_count:
            start = max(0, row_count - PROFILE_PAGE_SIZE)
            return await self._async_scan_pages(start_offset=start, forward=False)
        return await self._async_scan_pages(start_offset=0, forward=True)

    async def _async_scan_pages(
        self, start_offset: int, forward: bool
    ) -> dict | None:
        """Page until a matching location is found or the safety bound is reached."""
        offset = start_offset
        for _ in range(PROFILE_MAX_PAGES):
            rows = await self.provider.async_rows_page(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                limit=PROFILE_PAGE_SIZE,
                offset=offset,
                descending=True if self.timestamp_field else None,
            )
            if not rows:
                break
            match = select_location_row(rows, self.location_field, self.location_value)
            if match is not None:
                return match
            if forward:
                offset += len(rows)
                if len(rows) < PROFILE_PAGE_SIZE:
                    break
            else:
                if offset == 0:
                    break
                offset = max(0, offset - PROFILE_PAGE_SIZE)
        return None
