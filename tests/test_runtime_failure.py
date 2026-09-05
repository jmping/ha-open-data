import asyncio

from custom_components.open_data.runtime_failure import next_failure


def test_programming_failure_suspends_immediately() -> None:
    failure = next_failure(stage="normalize", err=TypeError("unexpected keyword"), previous=None)
    assert failure.transient is False
    assert failure.suspended is True
    assert failure.occurrences == 1


def test_repeated_timeout_trips_circuit_breaker() -> None:
    failure = None
    for occurrence in range(1, 4):
        failure = next_failure(
            stage="observation_fetch",
            err=asyncio.TimeoutError("upstream timeout"),
            previous=failure,
        )
        assert failure.occurrences == occurrence
        assert failure.transient is True
    assert failure is not None
    assert failure.suspended is True


def test_different_failure_resets_occurrence_counter() -> None:
    first = next_failure(
        stage="observation_fetch",
        err=asyncio.TimeoutError("upstream timeout"),
        previous=None,
    )
    second = next_failure(
        stage="metadata",
        err=asyncio.TimeoutError("metadata timeout"),
        previous=first,
    )
    assert second.occurrences == 1
    assert second.fingerprint != first.fingerprint
