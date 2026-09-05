from custom_components.open_data.data_semantics import (
    MEASURE_KIND_CUMULATIVE,
    MEASURE_KIND_DURATION,
    MEASURE_KIND_EVENT_COUNT,
    MEASURE_KIND_INSTANTANEOUS,
    MEASURE_KIND_INTERVAL_AMOUNT,
    TIME_ROLE_AS_OF,
    TIME_ROLE_EVENT,
    TIME_ROLE_OBSERVATION,
    TIME_ROLE_PREVIOUS_EVENT,
    TIME_ROLE_PUBLISHED,
    infer_measure_kind,
    infer_time_role,
    recommended_state_class,
)


def test_multiple_timestamp_fields_are_semantically_distinct() -> None:
    assert infer_time_role("event_time", "Event occurred") == TIME_ROLE_EVENT
    assert infer_time_role("as_of_date", "As of") == TIME_ROLE_AS_OF
    assert infer_time_role("prior_event_time", "Previous event") == TIME_ROLE_PREVIOUS_EVENT
    assert infer_time_role("published_at", "Published") == TIME_ROLE_PUBLISHED
    assert infer_time_role("measurement_time", "Observation time") == TIME_ROLE_OBSERVATION


def test_measure_classes_cover_observed_corpus_shapes() -> None:
    assert infer_measure_kind("temperature", "Air temperature", "degC") == MEASURE_KIND_INSTANTANEOUS
    assert infer_measure_kind("rain_15min", "15 minute interval rainfall", "mm") == MEASURE_KIND_INTERVAL_AMOUNT
    assert infer_measure_kind("total_volume", "Cumulative total volume", "m3") == MEASURE_KIND_CUMULATIVE
    assert infer_measure_kind("elapsed_minutes", "Elapsed minutes", "min") == MEASURE_KIND_DURATION
    assert infer_measure_kind("incident_count", "Incident count") == MEASURE_KIND_EVENT_COUNT


def test_measure_classes_drive_home_assistant_state_semantics() -> None:
    assert recommended_state_class(MEASURE_KIND_INSTANTANEOUS) == "measurement"
    assert recommended_state_class(MEASURE_KIND_INTERVAL_AMOUNT) == "total"
    assert recommended_state_class(MEASURE_KIND_CUMULATIVE) == "total_increasing"
    assert recommended_state_class(MEASURE_KIND_EVENT_COUNT) == "total_increasing"
