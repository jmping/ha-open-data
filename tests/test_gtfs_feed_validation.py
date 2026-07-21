"""Regression tests for GTFS static-feed detection."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from custom_components.open_data.feeds.gtfs import inspect_gtfs_archive


def _archive(*names: str) -> bytes:
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(name, "id,name\n1,Example\n")
    return payload.getvalue()


def test_valid_gtfs_is_detected_by_archive_contents() -> None:
    result = inspect_gtfs_archive(
        _archive(
            "agency.txt",
            "stops.txt",
            "routes.txt",
            "trips.txt",
            "stop_times.txt",
            "calendar_dates.txt",
            "shapes.txt",
            "translations.txt",
        )
    )

    assert result.valid is True
    assert result.has_service_calendar is True
    assert result.optional_members == (
        "calendar_dates.txt",
        "shapes.txt",
        "stop_times.txt",
        "translations.txt",
    )


def test_extensionless_and_nested_archives_are_supported() -> None:
    result = inspect_gtfs_archive(
        _archive(
            "feed/AGENCY.TXT",
            "feed/STOPS.TXT",
            "feed/ROUTES.TXT",
            "feed/TRIPS.TXT",
            "feed/STOP_TIMES.TXT",
            "feed/CALENDAR.TXT",
        )
    )

    assert result.valid is True
    assert result.nested_directory is True


def test_missing_required_tables_are_reported() -> None:
    result = inspect_gtfs_archive(
        _archive("agency.txt", "stops.txt", "calendar.txt")
    )

    assert result.valid is False
    assert result.missing_required == (
        "routes.txt",
        "stop_times.txt",
        "trips.txt",
    )


def test_service_calendar_is_required() -> None:
    result = inspect_gtfs_archive(
        _archive(
            "agency.txt",
            "stops.txt",
            "routes.txt",
            "trips.txt",
            "stop_times.txt",
        )
    )

    assert result.valid is False
    assert result.reason == "archive did not contain calendar.txt or calendar_dates.txt"


def test_non_zip_payload_is_rejected() -> None:
    result = inspect_gtfs_archive(b"<html>not a feed</html>")

    assert result.valid is False
    assert result.reason == "payload was not a ZIP archive"
