"""Provider-neutral portal, catalog, dataset, resource, and observable models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PortalDescriptor:
    provider: str
    url: str
    title: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogDescriptor:
    portal: PortalDescriptor
    catalog_id: str
    title: str | None = None


@dataclass(frozen=True, slots=True)
class ResourceDescriptor:
    resource_id: str
    format: str | None = None
    url: str | None = None
    queryable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class ObservableDescriptor:
    field: str
    title: str | None = None
    unit: str | None = None
    semantic: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetDescriptor:
    dataset_id: str
    title: str
    portal: PortalDescriptor | None = None
    catalog: CatalogDescriptor | None = None
    resources: tuple[ResourceDescriptor, ...] = ()
    observables: tuple[ObservableDescriptor, ...] = ()
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
