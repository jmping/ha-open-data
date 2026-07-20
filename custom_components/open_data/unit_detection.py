"""Provider-neutral measurement unit detection."""

from __future__ import annotations

from dataclasses import dataclass
import re

_ALIASES = {
    "c": "°C", "degc": "°C", "celsius": "°C", "°c": "°C",
    "f": "°F", "degf": "°F", "fahrenheit": "°F", "°f": "°F",
    "%": "%", "percent": "%", "percentage": "%",
    "ppm": "ppm", "ug/m3": "µg/m³", "µg/m³": "µg/m³",
    "m/s": "m/s", "km/h": "km/h", "kph": "km/h",
    "mm": "mm", "cm": "cm", "m": "m", "in": "in", "ft": "ft",
}


@dataclass(frozen=True, slots=True)
class UnitSemantic:
    """Canonical unit inference."""

    canonical: str
    score: int
    source: str


def detect_unit(unit: str | None, *, label: str | None = None) -> UnitSemantic | None:
    """Return a canonical unit from explicit metadata or a label suffix."""
    if unit:
        normalized = _normalize(unit)
        if canonical := _ALIASES.get(normalized):
            return UnitSemantic(canonical, 100, "metadata")
    if label:
        lowered = label.casefold()
        for alias, canonical in _ALIASES.items():
            if re.search(rf"(?:\(|\[|\s){re.escape(alias)}(?:\)|\]|$)", lowered):
                return UnitSemantic(canonical, 60, "label")
    return None


def _normalize(value: str) -> str:
    return value.strip().casefold().replace("μ", "µ").replace("³", "3").replace(" ", "")
