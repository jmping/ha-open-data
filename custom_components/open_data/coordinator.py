"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES
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
        identity_field: str | None = None,
        display_field: str | None = None,
        selected_records: tuple[str, ...] = (),
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
        self.identity_field = identity_field
        self.display_field = display_field
        self.selected_records = selected_records
        self.dataset: OpenDataDataset | None = None
        self.record_labels: dict[str, str] = {}

    async def _async_load_record_labels(self) -> None:
        if not self.identity_field or not self.selected_records:
            return
        rows = await self.provider.async_distinct_rows(
            self.dataset_id,
            self.resource_id,
            self.identity_field,
            self.display_field,
            tuple(),
            limit=max(100, len(self.selected_records) * 4),
        )
        selected = set(self.selected_records)
        for row in rows:
            value = row.get(self.identity_field)
            if value is None or str(value) not in selected:
                continue
            label = row.get(self.display_field) if self.display_field else None
            self.record_labels[str(value)] = str(label) if label not in (None, "") else str(value)

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            if self.dataset is None:
                self.dataset = await self.provider.async_get_dataset(
                    self.dataset_id, self.resource_id
                )
                self.resource_id = self.dataset.resource_id or self.resource_id
                await self._async_load_record_labels()

            if self.identity_field and self.selected_records:
                records: dict[str, dict] = {}
                for record_id in self.selected_records:
                    values = await self.provider.async_latest_row(
                        self.dataset_id,
                        self.resource_id,
                        self.timestamp_field,
                        filters={self.identity_field: record_id},
                    )
                    records[record_id] = values or {}
                    self.record_labels.setdefault(record_id, record_id)
                first = next((row for row in records.values() if row), {})
                return OpenDataSnapshot(
                    dataset=self.dataset,
                    values=first,
                    records=records,
                    record_labels=dict(self.record_labels),
                )

            values = await self.provider.async_latest_row(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                filters=None,
            )
            return OpenDataSnapshot(dataset=self.dataset, values=values or {})
        except (OpenDataError, ValueError) as err:
            raise UpdateFailed(str(err)) from err
