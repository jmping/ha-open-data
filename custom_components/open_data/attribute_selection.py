"""Select useful non-state attributes for planned entities."""

from __future__ import annotations

from typing import Iterable


def select_attributes(
    fields: Iterable[str],
    *,
    state_field: str,
    excluded: Iterable[str] = (),
    limit: int = 12,
) -> tuple[str, ...]:
    """Return stable, deduplicated attributes excluding state and internal fields."""
    excluded_names = {state_field, *excluded}
    selected: list[str] = []
    for field in fields:
        if field in excluded_names or field in selected:
            continue
        selected.append(field)
        if len(selected) >= max(0, limit):
            break
    return tuple(selected)
