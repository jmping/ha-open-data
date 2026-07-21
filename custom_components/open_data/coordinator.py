"""DataUpdateCoordinator for Open Data datasets."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL_MINUTES
from .models import OpenDataDataset, OpenDataSnapshot
from .providers.base import OpenDataError, OpenDataProvider
from .semantic_observations import normalize_observations

_MAX_CONCURRENT_RECORD_REQUESTS = 6


class OpenDataCoordinator(DataUpdateCoordinator[OpenDataSnapshot]):
    """Coordinate metadata, latest rows, and semantic observation streams."""

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
        *,
        observation_shape: str = "unknown",
        metric_dimension_fields: tuple[str, ...] = (),
        value_fields: tuple[str, ...] = (),
        observation_dimension_fields: tuple[str, ...] = (),
        unit_fields: tuple[str, ...] = (),
        retrieval_dimension_multiplier: int = 1,
        estimated_entity_count: int = 1,
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
        self.hierarchy_fields = hierarchy_fields
        self.observation_shape = observation_shape
        self.metric_dimension_fields = metric_dimension_fields
        self.value_fields = value_fields
        self.observation_dimension_fields = observation_dimension_fields
        self.unit_fields = unit_fields
        self.retrieval_dimension_multiplier = max(1, retrieval_dimension_multiplier)
        self.estimated_entity_count = max(1, estimated_entity_count)
        self.dataset: OpenDataDataset | None = None
        self.record_labels: dict[str, str] = {}

    @property
    def uses_semantic_observations(self) -> bool:
        """Return whether runtime rows should be pivoted into logical streams."""
        return bool(self.value_fields) and self.observation_shape in {
            "long",
            "multi_dimensional",
        }

    async def _async_load_record_labels(self) -> None:
        if not self.identity_field or not self.selected_records:
            return
        rows = await self.provider.async_distinct_rows(
            self.dataset_id,
            self.resource_id,
            self.identity_field,
            self.display_field,
            self.hierarchy_fields,
            limit=max(100, len(self.selected_records) * 4),
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

    async def _async_semantic_snapshot(self) -> OpenDataSnapshot:
        """Fetch enough recent physical rows to recover all current logical streams."""
        per_entity = max(25, self.retrieval_dimension_multiplier * 4)
        if self.selected_records and self.identity_field:
            rows = await self.provider.async_fetch_observations(
                self.dataset_id,
                self.resource_id,
                entity_field=self.identity_field,
                entity_values=self.selected_records,
                timestamp_field=self.timestamp_field,
                observations_per_entity=per_entity,
            )
        else:
            rows = await self.provider.async_sample_observations(
                self.dataset_id,
                self.resource_id,
                entity_field=self.identity_field,
                timestamp_field=self.timestamp_field,
                entity_limit=self.estimated_entity_count,
                observations_per_entity=per_entity,
            )
        observations = normalize_observations(
            rows,
            shape=self.observation_shape,
            entity_field=self.identity_field,
            timestamp_field=self.timestamp_field,
            metric_dimension_fields=self.metric_dimension_fields,
            value_fields=self.value_fields,
            observation_dimension_fields=self.observation_dimension_fields,
            unit_fields=self.unit_fields,
        )
        records: dict[str, dict] = {}
        for observation in observations.values():
            if observation.entity_id is not None:
                records.setdefault(observation.entity_id, observation.source_row)
                self.record_labels.setdefault(observation.entity_id, observation.entity_id)
        for record_id in self.selected_records:
            self.record_labels.setdefault(record_id, record_id)
        first = next((item.source_row for item in observations.values()), {})
        return OpenDataSnapshot(
            dataset=self.dataset,
            values=first,
            records=records,
            record_labels=dict(self.record_labels),
            observations=observations,
        )

    async def _async_update_data(self) -> OpenDataSnapshot:
        try:
            if self.dataset is None:
                self.dataset = await self.provider.async_get_dataset(
                    self.dataset_id, self.resource_id
                )
                self.resource_id = self.dataset.resource_id or self.resource_id
                await self._async_load_record_labels()

            if self.uses_semantic_observations:
                return await self._async_semantic_snapshot()

            if self.identity_field and self.selected_records:
                semaphore = asyncio.Semaphore(_MAX_CONCURRENT_RECORD_REQUESTS)
                results = await asyncio.gather(
                    *(
                        self._async_latest_record(record_id, semaphore)
                        for record_id in self.selected_records
                    )
                )
                records = dict(results)
                for record_id in self.selected_records:
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
