"""Catalog-quality signals used to rank large public-data tenants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import OpenDataDataset


@dataclass(slots=True, frozen=True)
class CatalogQuality:
    """Provider-independent quality adjustment with explainable reasons."""

    adjustment: int
    reasons: tuple[str, ...]


def _strings(value: Any) -> list[str]:
    """Flatten useful textual metadata without depending on one provider shape."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            if key.casefold() in {
                "name",
                "display_name",
                "title",
                "description",
                "attribution",
                "source",
                "provenance",
                "owner",
                "publisher",
                "type",
                "viewtype",
            }:
                result.extend(_strings(item))
        return result
    return []


def catalog_quality(dataset: OpenDataDataset) -> CatalogQuality:
    """Prefer authoritative queryable sources over copies and presentation views."""
    raw = dataset.raw if isinstance(dataset.raw, dict) else {}
    resource = raw.get("resource") if isinstance(raw.get("resource"), dict) else {}
    classification = (
        raw.get("classification")
        if isinstance(raw.get("classification"), dict)
        else {}
    )
    metadata = " ".join(
        _strings(raw)
        + _strings(resource)
        + _strings(classification)
        + [dataset.title, dataset.description or ""]
    ).casefold()

    adjustment = 0
    reasons: list[str] = []

    view_type = str(
        resource.get("type")
        or resource.get("viewType")
        or raw.get("viewType")
        or ""
    ).casefold()
    if view_type in {"dataset", "table", "tabular"}:
        adjustment += 12
        reasons.append("source dataset")
    elif view_type in {"chart", "filter", "map", "story", "visualization"}:
        adjustment -= 18
        reasons.append(f"presentation view:{view_type}")

    official_markers = (
        "city of new york",
        "nyc open data",
        "department of",
        "official",
        "agency",
        "government",
    )
    if any(marker in metadata for marker in official_markers):
        adjustment += 10
        reasons.append("official publisher metadata")

    derived_markers = (
        "community created",
        "community view",
        "derived view",
        "filtered view",
        "copy of ",
        "test dataset",
        "sample dataset",
    )
    if any(marker in metadata for marker in derived_markers):
        adjustment -= 30
        reasons.append("derived or community copy")

    if resource.get("parent_fxf") or raw.get("parent_fxf") or raw.get("parentId"):
        adjustment -= 14
        reasons.append("derived from another dataset")

    rows_updated = resource.get("rowsUpdatedAt") or raw.get("rowsUpdatedAt")
    if rows_updated:
        adjustment += 4
        reasons.append("update metadata available")

    columns = resource.get("columns_field_name") or resource.get("columns_name")
    if isinstance(columns, list) and columns:
        adjustment += 6
        reasons.append("catalog schema available")

    return CatalogQuality(adjustment, tuple(dict.fromkeys(reasons)))
