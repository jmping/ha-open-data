"""Plan logical devices independently of Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .entity_planning import EntityPlan


@dataclass(frozen=True, slots=True)
class DevicePlan:
    """A logical device and its planned entities."""

    device_key: str
    name: str
    entity_keys: tuple[str, ...]


def plan_device(device_key: str, name: str, entities: Iterable[EntityPlan]) -> DevicePlan:
    """Group entity plans under one stable logical device."""
    keys = tuple(sorted((entity.unique_key for entity in entities), key=str.casefold))
    return DevicePlan(device_key=device_key, name=name.strip() or device_key, entity_keys=keys)
