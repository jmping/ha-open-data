"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataError, OpenDataProvider

_MAX_CONCURRENT_RECORD_REQUESTS = 6
_MAX_LABEL_ROWS = 2000
_LOGGER = logging.getLogger(__name__)


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
        hierarchy_fields: tuple[str, ...] = (),
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Open Data {dataset_id}",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.provider = provider
        self.dataset_id = dataset_id
        self.resource_id = resource_id
        self.timestamp_field = timestamp_field
        self.identity_field = identity_field
        self.display_field = display_field
        self.selected_records = tuple(dict.fromkeys(str(item) for item in selected_records))
        self.hierarchy_fields = hierarchy_fields
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
            self.hierarchy_fields,
            limit=min(
                _MAX_LABEL_ROWS,
                max(100, len(self.selected_records) * 4),
            ),
        )
        selected = set(self.selected_records)
        labels: dict[str, list[str]] = {}
        contexts: dict[str, tuple[str, ...]] = {}
        for row in rows:
            value = row.get(self.identity_field)
            if value is None or str(value) not in selected:
                continue
            record_id = str(value)
            raw_label = row.get(self.display_field) if self.display_field else None
            label = str(raw_label) if raw_label not in (None, "") else record_id
            labels.setdefault(label, []).append(record_id)
            contexts[record_id] = tuple(
                str(row[field])
                for field in self.hierarchy_fields
                if row.get(field) not in (None, "")
            )
            self.record_labels[record_id] = label

        # Labels such as "Precinct 1" are often only unique within their parent
        # geography. Add available hierarchy context only where it is needed.
        for label, record_ids in labels.items():
            if len(record_ids) < 2:
                continue
            for record_id in record_ids:
                context = contexts.get(record_id, ())
                if context:
                    self.record_labels[record_id] = f"{label} — {' / '.join(context)}"
                else:
                    self.record_labels[record_id] = f"{label} — {record_id}"

    async def _async_latest_record(
        self, record_id: str, semaphore: asyncio.Semaphore
    ) -> tuple[str, dict]:
        """Fetch one latest observation without overwhelming a portal."""
        async with semaphore:
            values = await self.provider.async_latest_row(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                filters={self.identity_field: record_id},
            )
        return record_id, values or {}

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            if self.dataset is None:
                self.dataset = await self.provider.async_get_dataset(
                    self.dataset_id, self.resource_id
                )
                self.resource_id = self.dataset.resource_id or self.resource_id
                await self._async_load_record_labels()

            if self.identity_field and self.selected_records:
                semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RECORD_REQUESTS)
                raw_results = await asyncio.gather(
                    *(
                        self._async_latest_record(record_id, semaphore)
                        for record_id in self.selected_records
                    ),
                    return_exceptions=True,
                )
                results: list[tuple[str, dict]] = []
                failures: list[BaseException] = []
                for result in raw_results:
                    if isinstance(result, BaseException):
                        failures.append(result)
                    else:
                        results.append(result)

                # One unavailable or malformed record should not take down every
                # other selected location. Only fail the coordinator when all
                # requests failed and there is no usable snapshot to publish.
                if failures and not results:
                    first_failure = failures[0]
                    if isinstance(first_failure, (OpenDataError, ValueError)):
                        raise first_failure
                    raise UpdateFailed(str(first_failure)) from first_failure
                if failures:
                    _LOGGER.warning(
                        "Skipped %s of %s selected Open Data records during refresh",
                        len(failures),
                        len(raw_results),
                    )

                # A selected record is not necessarily a current entity. Providers
                # may return no row for old observation IDs, unavailable stations,
                # or values that no longer exist after the identity field changes.
                records = {
                    record_id: values
                    for record_id, values in results
                    if values
                }
                labels = {
                    record_id: self.record_labels.get(record_id, record_id)
                    for record_id in records
                }
                first = next(iter(records.values()), {})
                return OpenDataSnapshot(
                    dataset=self.dataset,
                    values=first,
                    records=records,
                    record_labels=labels,
                )

            values = await self.provider.async_latest_row(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                filters=None,
            )
            return OpenDataSnapshot(dataset=self.dataset, values=values or {})
        except UpdateFailed:
            raise
        except (OpenDataError, ValueError) as err:
            raise UpdateFailed(str(err)) from err
