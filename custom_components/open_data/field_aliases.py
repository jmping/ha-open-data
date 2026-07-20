"""Canonical aliases used by provider-neutral semantic inference."""

from __future__ import annotations

import re

_ALIASES = {
    "temp": "temperature",
    "air_temp": "temperature",
    "air_temperature": "temperature",
    "temperature_c": "temperature",
    "temperature_f": "temperature",
    "rh": "relative_humidity",
    "humidity": "relative_humidity",
    "pm25": "particulate_matter_2_5",
    "pm2_5": "particulate_matter_2_5",
    "pm_2_5": "particulate_matter_2_5",
    "pm10": "particulate_matter_10",
    "rain": "precipitation",
    "rainfall": "precipitation",
    "wind_spd": "wind_speed",
    "windspeed": "wind_speed",
    "stationid": "station_id",
    "site_id": "station_id",
}


def normalize_field_alias(value: str) -> str:
    """Return a stable canonical concept name for a field-like string."""
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    return _ALIASES.get(normalized, normalized)
