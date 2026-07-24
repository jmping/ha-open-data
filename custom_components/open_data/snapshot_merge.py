"""Non-destructive snapshot helpers for partial provider refreshes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from .models import OpenDataSnapshot, SemanticObservation


def carry_forward_failed_records(
    previous: OpenDataSnapshot | None,
    records: Mapping[str, dict],
    observations: Mapping[str, SemanticObservation],
    failed_record_ids: Iterable[str],
) -> tuple[dict[str, dict], dict[str, SemanticObservation]]:
    """Carry forward only records whose refresh request failed.

    A successful empty response is not carried forward because it may represent a
    retired or currently absent record. A request exception is different: it is
    not evidence that the prior state disappeared.
    """
    merged_records = dict(records)
    merged_observations = dict(observations)
    if previous is None:
        return merged_records, merged_observations

    failed = set(failed_record_ids)
    for record_id in failed:
        previous_record = previous.records.get(record_id)
        if previous_record is not None and record_id not in merged_records:
            merged_records[record_id] = previous_record

    for stream_id, observation in previous.observations.items():
        if observation.unit_id in failed and stream_id not in merged_observations:
            merged_observations[stream_id] = observation

    return merged_records, merged_observations
