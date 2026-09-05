from custom_components.open_data.local_discovery import rank_local_sources


def test_ann_arbor_location_surfaces_local_state_and_national_sources() -> None:
    ranked = rank_local_sources(42.2808, -83.7430)
    by_id = {item.profile.source_id: item for item in ranked}

    assert by_id["ann_arbor_open_data"].applies_here is True
    assert by_id["ann_arbor_open_data"].profile.validation_status == "partial"
    assert "last checked 2026-09-05" in by_id["ann_arbor_open_data"].profile.validation_label
    assert by_id["michigan_open_data"].applies_here is True
    assert by_id["nws_us"].applies_here is True
    assert by_id["semcog"].distance_km is not None


def test_tested_status_is_independent_from_importability() -> None:
    ranked = rank_local_sources(42.2808, -83.7430)
    profiles = {item.profile.source_id: item.profile for item in ranked}

    assert profiles["ann_arbor_open_data"].importable is True
    assert profiles["ann_arbor_open_data"].validation_status == "partial"
    assert profiles["nws_us"].importable is False
    assert profiles["nws_us"].validation_status == "discovery_only"
