"""Persistent portal preparation state for deferred configuration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .discovery import DatasetCandidate, score_dataset
from .models import OpenDataDataset, OpenDataField

STORAGE_KEY = "open_data.prepared_sites"
STORAGE_VERSION = 1
DATA_PREPARATIONS = "preparations"


@dataclass(slots=True, frozen=True)
class PreparedSite:
    """One persistable portal preparation result."""

    portal_url: str
    provider: str | None
    status: str
    updated_at: str
    candidates: tuple[DatasetCandidate, ...] = ()
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "portal_url": self.portal_url,
            "provider": self.provider,
            "status": self.status,
            "updated_at": self.updated_at,
            "error": self.error,
            "datasets": [_dataset_as_dict(item.dataset) for item in self.candidates],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> PreparedSite:
        datasets = tuple(
            score_dataset(_dataset_from_dict(item))
            for item in value.get("datasets", ())
            if isinstance(item, dict)
        )
        return cls(
            portal_url=str(value["portal_url"]),
            provider=value.get("provider"),
            status=str(value.get("status", "failed")),
            updated_at=str(value.get("updated_at", "")),
            candidates=datasets,
            error=value.get("error"),
        )


class PreparationRegistry:
    """Persist preparation results and own background tasks."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._sites: dict[str, PreparedSite] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self._sites = {
            key: PreparedSite.from_dict(value)
            for key, value in stored.get("sites", {}).items()
            if isinstance(value, dict)
        }
        # A task cannot survive a HA restart. Make interrupted work retryable.
        for key, site in tuple(self._sites.items()):
            if site.status == "preparing":
                self._sites[key] = PreparedSite(
                    site.portal_url, site.provider, "failed", _now(), error="interrupted"
                )
        await self._async_save()

    def get(self, portal_url: str) -> PreparedSite | None:
        return self._sites.get(_key(portal_url))

    def start(
        self,
        portal_url: str,
        prepare: Callable[[], Awaitable[tuple[str, str, list[DatasetCandidate]]]],
    ) -> asyncio.Task[None]:
        key = _key(portal_url)
        running = self._tasks.get(key)
        if running and not running.done():
            return running
        self._sites[key] = PreparedSite(portal_url, None, "preparing", _now())
        task = asyncio.create_task(self._run(key, prepare))
        self._tasks[key] = task
        return task

    async def _run(
        self,
        key: str,
        prepare: Callable[[], Awaitable[tuple[str, str, list[DatasetCandidate]]]],
    ) -> None:
        await self._async_save()
        try:
            portal_url, provider, candidates = await prepare()
        except Exception as err:  # noqa: BLE001
            self._sites[key] = PreparedSite(
                self._sites[key].portal_url,
                None,
                "failed",
                _now(),
                error=type(err).__name__,
            )
        else:
            self._sites[key] = PreparedSite(
                portal_url, provider, "ready", _now(), tuple(candidates)
            )
        finally:
            await self._async_save()
            self._tasks.pop(key, None)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"sites": {key: site.as_dict() for key, site in self._sites.items()}}
        )


def _key(url: str) -> str:
    return url.strip().rstrip("/").casefold()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _dataset_as_dict(dataset: OpenDataDataset) -> dict[str, Any]:
    return {
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "description": dataset.description,
        "resource_id": dataset.resource_id,
        "fields": [
            {
                "name": field.name,
                "label": field.label,
                "data_type": field.data_type,
                "description": field.description,
            }
            for field in dataset.fields
        ],
        "raw": dataset.raw,
    }


def _dataset_from_dict(value: dict[str, Any]) -> OpenDataDataset:
    return OpenDataDataset(
        dataset_id=str(value["dataset_id"]),
        title=str(value["title"]),
        description=value.get("description"),
        resource_id=value.get("resource_id"),
        fields=tuple(OpenDataField(**field) for field in value.get("fields", ())),
        raw=dict(value.get("raw", {})),
    )
