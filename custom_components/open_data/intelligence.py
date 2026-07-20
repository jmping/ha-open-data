"""Persistent adaptive profiling for large open-data datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, PROFILE_SAMPLE_SIZE
from .providers.base import OpenDataProvider

STORE_VERSION = 1


@dataclass(slots=True)
class DatasetProfile:
    """Learned information about where and how a dataset changes."""

    row_count: int | None = None
    ordering: str = "unknown"
    newest_region: str = "unknown"
    confidence: float = 0.0
    sample_hashes: dict[str, str] = field(default_factory=dict)
    changed_regions: dict[str, int] = field(default_factory=dict)
    observations: int = 0
    last_profiled: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "DatasetProfile":
        """Create a profile from stored JSON-compatible data."""
        if not isinstance(value, dict):
            return cls()
        return cls(
            row_count=value.get("row_count"),
            ordering=str(value.get("ordering", "unknown")),
            newest_region=str(value.get("newest_region", "unknown")),
            confidence=float(value.get("confidence", 0.0)),
            sample_hashes=dict(value.get("sample_hashes", {})),
            changed_regions={
                str(key): int(count)
                for key, count in dict(value.get("changed_regions", {})).items()
            },
            observations=int(value.get("observations", 0)),
            last_profiled=value.get("last_profiled"),
        )


class DatasetIntelligence:
    """Probe beginning, middle, and end and persist learned behavior."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        provider: OpenDataProvider,
        dataset_id: str,
        resource_id: str | None,
        timestamp_field: str | None,
    ) -> None:
        self.provider = provider
        self.dataset_id = dataset_id
        self.resource_id = resource_id
        self.timestamp_field = timestamp_field
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.profile.{entry_id}"
        )
        self.profile = DatasetProfile()

    async def async_load(self) -> DatasetProfile:
        """Load the cached profile."""
        self.profile = DatasetProfile.from_dict(await self._store.async_load())
        return self.profile

    async def async_profile(self) -> DatasetProfile:
        """Take sparse probes and update the learned profile."""
        row_count = await self.provider.async_row_count(
            self.dataset_id, self.resource_id
        )
        offsets = _probe_offsets(row_count, PROFILE_SAMPLE_SIZE)
        hashes: dict[str, str] = {}
        samples: dict[str, list[dict[str, Any]]] = {}
        for region, offset in offsets.items():
            rows = await self.provider.async_rows_page(
                self.dataset_id,
                self.resource_id,
                self.timestamp_field,
                limit=PROFILE_SAMPLE_SIZE,
                offset=offset,
                descending=None,
            )
            samples[region] = rows
            hashes[region] = _rows_hash(rows)

        previous = self.profile.sample_hashes
        changed = [region for region, digest in hashes.items() if previous.get(region) != digest]
        for region in changed:
            self.profile.changed_regions[region] = self.profile.changed_regions.get(region, 0) + 1

        self.profile.row_count = row_count
        self.profile.sample_hashes = hashes
        self.profile.observations += 1
        self.profile.last_profiled = datetime.now(UTC).isoformat()
        self.profile.ordering = _infer_ordering(samples, self.timestamp_field)
        self.profile.newest_region, self.profile.confidence = _infer_newest_region(
            self.profile, changed
        )
        await self._store.async_save(asdict(self.profile))
        return self.profile


def _probe_offsets(row_count: int | None, sample_size: int) -> dict[str, int]:
    """Return sparse beginning/middle/end page offsets."""
    if row_count is None or row_count <= sample_size:
        return {"beginning": 0}
    end = max(0, row_count - sample_size)
    middle = max(0, (row_count // 2) - (sample_size // 2))
    offsets = {"beginning": 0, "middle": middle, "end": end}
    return dict.fromkeys(offsets).keys() and offsets


def _rows_hash(rows: list[dict[str, Any]]) -> str:
    """Produce a stable compact fingerprint for a page."""
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _infer_ordering(
    samples: dict[str, list[dict[str, Any]]], timestamp_field: str | None
) -> str:
    """Infer ascending or descending timestamp order from sparse samples."""
    if not timestamp_field:
        return "unknown"
    values: list[str] = []
    for region in ("beginning", "middle", "end"):
        rows = samples.get(region, [])
        for row in (rows[:1] + rows[-1:]):
            value = row.get(timestamp_field)
            if value is not None:
                values.append(str(value))
    if len(values) < 2:
        return "unknown"
    if values == sorted(values):
        return "ascending_timestamp"
    if values == sorted(values, reverse=True):
        return "descending_timestamp"
    return "unstable"


def _infer_newest_region(
    profile: DatasetProfile, changed: list[str]
) -> tuple[str, float]:
    """Infer where new data appears using ordering and repeated hash changes."""
    if profile.ordering == "ascending_timestamp":
        return "end", 1.0
    if profile.ordering == "descending_timestamp":
        return "beginning", 1.0
    counts = profile.changed_regions
    total = sum(counts.values())
    if total == 0:
        return profile.newest_region, max(0.0, profile.confidence * 0.9)
    winner = max(counts, key=counts.get)
    confidence = counts[winner] / total
    if len(changed) > 1 and "middle" in changed:
        return "unstable", min(confidence, 0.5)
    return winner, confidence
