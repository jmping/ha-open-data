"""Helpers for translating provider metadata into shared descriptors."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .descriptors import DatasetDescriptor, PortalDescriptor, ResourceDescriptor


def map_resource(metadata: Mapping[str, Any]) -> ResourceDescriptor:
    """Map common provider resource keys into a normalized descriptor."""
    resource_id = str(metadata.get("id") or metadata.get("resource_id") or "").strip()
    if not resource_id:
        raise ValueError("resource metadata requires an id")
    return ResourceDescriptor(
        resource_id=resource_id,
        format=_optional_text(metadata.get("format")),
        url=_optional_text(metadata.get("url")),
        queryable=bool(metadata.get("queryable", False)),
        metadata=dict(metadata),
    )


def map_dataset(
    metadata: Mapping[str, Any],
    *,
    portal: PortalDescriptor | None = None,
    resources: Iterable[Mapping[str, Any]] = (),
) -> DatasetDescriptor:
    """Map common provider dataset keys into a normalized descriptor."""
    dataset_id = str(metadata.get("id") or metadata.get("dataset_id") or "").strip()
    title = str(metadata.get("title") or metadata.get("name") or "").strip()
    if not dataset_id or not title:
        raise ValueError("dataset metadata requires id and title")
    return DatasetDescriptor(
        dataset_id=dataset_id,
        title=title,
        portal=portal,
        resources=tuple(map_resource(item) for item in resources),
        description=_optional_text(metadata.get("description") or metadata.get("notes")),
        metadata=dict(metadata),
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
