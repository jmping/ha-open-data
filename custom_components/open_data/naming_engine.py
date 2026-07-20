"""Generate deterministic human-readable names for planned objects."""

from __future__ import annotations

import re


def humanize(value: str) -> str:
    """Convert identifiers into stable title-cased labels."""
    words = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().split()
    return " ".join(word.upper() if word.casefold() in {"pm2", "pm25", "pm10"} else word.capitalize() for word in words)


def entity_name(dataset_title: str, observable_kind: str, *, include_dataset: bool = False) -> str:
    """Build an entity display name."""
    observable = humanize(observable_kind.replace("particulate_matter_2_5", "PM2.5").replace("particulate_matter_10", "PM10"))
    return f"{dataset_title.strip()} {observable}" if include_dataset else observable


def device_name(dataset_title: str, location_name: str | None = None) -> str:
    """Build a logical device name."""
    return " ".join(part for part in (location_name, dataset_title.strip()) if part)
