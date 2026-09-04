"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES
from .entity_identity import looks_like_observation_id
from .freshness import apply_observation_freshness
from .history import snapshot_freshness
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataError, OpenDataProvider
from .record_structure import (
    RecordStructure,
    build_record_selections,
    decode_unit_key,
)
from .snapshot_merge import carry_forward_failed_records
from .temporal_runtime import normalize_observations

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
            limit=max(200, len(self.selected_records) * 4),
        )
        selections = build_record_selections(rows, self.record_structure)
        selected = set(self.selected_records)
        self.record_labels = {
            item.value: item.label for item in selections if item.value in selected
        }

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            dataset = await self.provider.async_get_dataset(
                self.dataset_id, self.resource_id
            )
            self.dataset = dataset
            if self.selected_records:
                await self._async_load_record_labels()
                records = await self._async_fetch_selected_records(dataset)
                values = self._latest_values_from_records(records)
                observations = self._normalize_record_observations(records)
            else:
                rows = await self.provider.async_observation_rows(
                    dataset.dataset_id,
                    dataset.resource_id,
                    self.timestamp_field,
                    limit=250,
                )
                if not rows:
                    latest = await self.provider.async_latest_row(
                        dataset.dataset_id,
                        dataset.resource_id,
                        self.timestamp_field,
                    )
                    rows = [latest] if latest else []
                records = {}
                values = rows[0] if rows else {}
                observations = normalize_observations(
                    rows,
                    field_roles=self.field_roles,
                    structure=self.record_structure,
                    selected_fields=self.selected_fields,
                )
            observations = apply_observation_freshness(
                observations,
                now=datetime.now(timezone.utc),
                update_interval=self.update_interval,
            )
            snapshot = OpenDataSnapshot(
                dataset=dataset,
                values=values,
                records=records,
                observations=observations,
                freshness=snapshot_freshness(observations),
            )
            return carry_forward_failed_records(self.data, snapshot)
        except OpenDataError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_fetch_selected_records(
        self, dataset: OpenDataDataset
    ) -> dict[str, dict]:
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RECORD_REQUESTS)

        async def _fetch(record_id: str) -> tuple[str, dict | None]:
            async with semaphore:
                filters = self._filters_for_record(record_id)
                row = await self.provider.async_latest_row(
                    dataset.dataset_id,
                    dataset.resource_id,
                    self.timestamp_field,
                    filters,
                )
                return record_id, row

        results = await asyncio.gather(
            *(_fetch(record_id) for record_id in self.selected_records),
            return_exceptions=True,
        )
        records: dict[str, dict] = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            record_id, row = result
            if row:
                records[record_id] = row
        return records

    def _filters_for_record(self, record_id: str) -> dict[str, str]:
        key_fields = self.record_structure.unit_key_fields
        if not key_fields and self.identity_field:
            key_fields = (self.identity_field,)
        if not key_fields:
            return {}
        values = decode_unit_key(record_id)
        if len(values) != len(key_fields):
            return {key_fields[0]: record_id}
        return dict(zip(key_fields, values, strict=True))

    @staticmethod
    def _latest_values_from_records(records: dict[str, dict]) -> dict:
        return next(iter(records.values()), {})

    def _normalize_record_observations(
        self, records: dict[str, dict]
    ) -> dict:
        observations = {}
        for record_id, row in records.items():
            observations.update(
                normalize_observations(
                    [row],
                    field_roles=self.field_roles,
                    structure=self.record_structure,
                    selected_fields=self.selected_fields,
                    unit_id=record_id,
                )
            )
        return observations
