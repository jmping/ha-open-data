"""Generate concise provider-neutral dataset summaries."""

from __future__ import annotations

from .dataset_profile import DatasetProfile
from .dataset_type import DatasetTypeInference


def summarize_dataset(
    title: str,
    profile: DatasetProfile,
    dataset_type: DatasetTypeInference,
) -> str:
    """Return a deterministic human-readable summary."""
    traits: list[str] = [dataset_type.kind.value.replace("_", " ")]
    if profile.timestamp:
        traits.append(f"time field {profile.timestamp}")
    if profile.latitude and profile.longitude:
        traits.append(f"coordinates {profile.latitude}/{profile.longitude}")
    elif profile.geometry:
        traits.append(f"geometry field {profile.geometry}")
    if profile.identifier:
        traits.append(f"identifier {profile.identifier}")
    if profile.measures:
        preview = ", ".join(profile.measures[:3])
        suffix = " and more" if len(profile.measures) > 3 else ""
        traits.append(f"measurements {preview}{suffix}")
    return f"{title}: " + "; ".join(traits) + "."
