"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES
from .entity_identity import looks_like_observation_id
from .freshness import apply_observation_freshness
from .history import snapshot_freshness
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataProvider
from .record_structure import (
    RecordStructure,
    build_record_selections,
    decode_unit_key,
)
from .runtime_failure import RuntimeFailure, next_failure
from .snapshot_merge import carry_forward_failed_snapshot
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
        temporal_plan: Mapping[str, Any] | None = None,
        timezone_name: str | None = None,
    ) -> None:
        normal_interval = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=f"Open Data {dataset_id}",
            update_interval=normal_interval,
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
        self.temporal_plan = dict(temporal_plan or {})
        self.timezone_name = timezone_name
        self.dataset: OpenDataDataset | None = None
        self.record_labels: dict[str, str] = {}
        self.runtime_failure: RuntimeFailure | None = None
        self._normal_update_interval = normal_interval

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
        """Refresh one dataset and stop automatic retries for deterministic failures."""
        stage = "metadata"
        try:
            dataset = await self.provider.async_get_dataset(
                self.dataset_id, self.resource_id
            )
            self.dataset = dataset
            if self.selected_records:
                stage = "record_labels"
                await self._async_load_record_labels()
                stage = "record_fetch"
                records, failed_record_ids = await self._async_fetch_selected_records(
                    dataset
                )
                values = self._latest_values_from_records(records)
                stage = "normalize"
                observations = self._normalize_record_observations(records)
            else:
                failed_record_ids = ()
                stage = "observation_fetch"
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
                stage = "normalize"
                observations = normalize_observations(
                    rows,
                    field_roles=self.field_roles,
                    structure=self.record_structure,
                    selected_fields=self.selected_fields,
                    temporal_plan=self.temporal_plan,
                    timezone_name=self.timezone_name,
                )

            stage = "freshness"
            observations = apply_observation_freshness(
                observations,
                self._normal_update_interval.total_seconds(),
            )
            latest_observation_at, source_updated_at, frequency_seconds = (
                snapshot_freshness(dataset, observations)
            )
            stage = "snapshot"
            snapshot = OpenDataSnapshot(
                dataset=dataset,
                values=values,
                records=records,
                record_labels=dict(self.record_labels),
                observations=observations,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                latest_observation_at=latest_observation_at,
                source_updated_at=source_updated_at,
                update_frequency_seconds=frequency_seconds,
            )
            self.runtime_failure = None
            if self.update_interval is None:
                self.update_interval = self._normal_update_interval
            return carry_forward_failed_snapshot(
                self.data, snapshot, failed_record_ids
            )
        except Exception as err:  # noqa: BLE001 - normalize all refresh failures
            failure = next_failure(
                stage=stage,
                err=err,
                previous=self.runtime_failure,
            )
            self.runtime_failure = failure
            if failure.suspended:
                # A deterministic parser/schema/programming failure should not make
                # Home Assistant retry setup or poll indefinitely. Setting the
                # interval to None leaves manual reload/retry available.
                self.update_interval = None
            retry_state = "automatic refresh suspended" if failure.suspended else "will retry"
            raise UpdateFailed(
                f"{stage} failed ({failure.error_type}); {retry_state}: "
                f"{failure.message}"
            ) from err

    async def _async_fetch_selected_records(
        self, dataset: OpenDataDataset
    ) -> tuple[dict[str, dict], tuple[str, ...]]:
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
        failed_record_ids: list[str] = []
        for requested_id, result in zip(self.selected_records, results, strict=True):
            if isinstance(result, BaseException):
                failed_record_ids.append(requested_id)
                continue
            record_id, row = result
            if row:
                records[record_id] = row
        return records, tuple(failed_record_ids)

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

    def _normalize_record_observations(self, records: dict[str, dict]) -> dict:
        observations = {}
        for record_id, row in records.items():
            observations.update(
                normalize_observations(
                    [row],
                    field_roles=self.field_roles,
                    structure=self.record_structure,
                    selected_fields=self.selected_fields,
                    unit_id=record_id,
                    temporal_plan=self.temporal_plan,
                    timezone_name=self.timezone_name,
                )
            )
        return observations
