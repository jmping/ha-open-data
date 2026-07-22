"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES
from .entity_identity import looks_like_observation_id
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataError, OpenDataProvider
from .record_structure import (
    RecordStructure,
    build_record_selections,
    decode_unit_key,
)
from .semantic_observations import normalize_observations

_MAX_CONCURRENT_RECORD_REQUESTS = 6


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
        record_structure: RecordStructure | None = None,
        field_roles: dict[str, str] | None = None,
        selected_fields: tuple[str, ...] | None = None,
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
        # Observation IDs identify historical rows, not persistent Home Assistant
        # entities. Even old configurations that saved those values must fall back
        # to a single latest-dataset snapshot instead of creating one entity per row.
        self.selected_records = (
            () if looks_like_observation_id(identity_field) else selected_records
        )
        self.hierarchy_fields = hierarchy_fields
        self.record_structure = record_structure or RecordStructure(())
        self.field_roles = field_roles or {}
        self.selected_fields = selected_fields
        self.dataset: OpenDataDataset | None = None
        self.record_labels: dict[str, str] = {}

    async def _async_load_record_labels(self) -> None:
        key_fields = self.record_structure.unit_key_fields
        if not key_fields and self.identity_field:
            key_fields = (self.identity_field,)
        if not key_fields or not self.selected_records:
            return
        label_fields = self.record_structure.unit_label_fields
        if not label_fields and self.display_field:
            label_fields = (self.display_field,)
        requested_fields = tuple(
            dict.fromkeys((*key_fields[1:], *label_fields, *self.hierarchy_fields))
        )
        rows = await self.provider.async_distinct_rows(
            self.dataset_id,
            self.resource_id,
            key_fields[0],
            None,
            requested_fields,
            limit=max(100, len(self.selected_records) * 4),
        )
        if self.record_structure.unit_key_fields:
            for selection in build_record_selections(rows, self.record_structure):
                if selection.value in self.selected_records:
                    self.record_labels[selection.value] = selection.label
            return

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
            key_fields = self.record_structure.unit_key_fields
            filters = (
                decode_unit_key(record_id, key_fields)
                if key_fields
                else {self.identity_field: record_id}
            )
            if not filters:
                raise ValueError("Selected record does not match its configured unit key")
            rows = await self.provider.async_observation_rows(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                filters=filters,
            )
        return record_id, rows

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            if self.dataset is None:
                self.dataset = await self.provider.async_get_dataset(
                    self.dataset_id, self.resource_id
                )
                self.resource_id = self.dataset.resource_id or self.resource_id
                await self._async_load_record_labels()

            if (self.identity_field or self.record_structure.unit_key_fields) and self.selected_records:
                semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RECORD_REQUESTS)
                results = await asyncio.gather(
                    *(
                        self._async_latest_record(record_id, semaphore)
                        for record_id in self.selected_records
                    ),
                    return_exceptions=True,
                )
                records: dict[str, dict] = {}
                observations = {}
                failures = 0
                for record_id, result in zip(self.selected_records, results, strict=True):
                    if isinstance(result, Exception):
                        failures += 1
                        self.logger.warning(
                            "Unable to refresh open-data record %s: %s",
                            record_id,
                            result,
                        )
                        continue
                    returned_id, rows = result
                    if rows:
                        records[returned_id] = rows[0]
                        observations.update(
                            normalize_observations(
                                rows,
                                field_roles=self.field_roles,
                                structure=self.record_structure,
                                selected_fields=self.selected_fields,
                                unit_id=returned_id,
                            )
                        )
                if failures == len(results) and results:
                    first_error = next(
                        result for result in results if isinstance(result, Exception)
                    )
                    raise UpdateFailed(str(first_error))
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
                    observations=observations,
                )

            rows = await self.provider.async_observation_rows(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                filters=None,
            )
            values = rows[0] if rows else {}
            return OpenDataSnapshot(
                dataset=self.dataset,
                values=values,
                observations=normalize_observations(
                    rows,
                    field_roles=self.field_roles,
                    structure=self.record_structure,
                    selected_fields=self.selected_fields,
                ),
            )
        except UpdateFailed:
            raise
        except (OpenDataError, ValueError) as err:
            raise UpdateFailed(str(err)) from err
