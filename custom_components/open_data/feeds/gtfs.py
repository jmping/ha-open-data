"""Bounded validation for GTFS static ZIP archives."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

GTFS_REQUIRED_FILES = frozenset(
    {"agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
)
GTFS_SERVICE_FILES = frozenset({"calendar.txt", "calendar_dates.txt"})
GTFS_OPTIONAL_FILES = frozenset(
    {
        "areas.txt",
        "attributions.txt",
        "booking_rules.txt",
        "fare_attributes.txt",
        "fare_leg_join_rules.txt",
        "fare_leg_rules.txt",
        "fare_media.txt",
        "fare_products.txt",
        "fare_rules.txt",
        "fare_transfer_rules.txt",
        "feed_info.txt",
        "frequencies.txt",
        "levels.txt",
        "location_group_stops.txt",
        "location_groups.txt",
        "networks.txt",
        "pathways.txt",
        "route_networks.txt",
        "shapes.txt",
        "stop_areas.txt",
        "stop_times.txt",
        "timeframes.txt",
        "transfers.txt",
        "translations.txt",
    }
)
MAX_GTFS_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_GTFS_MEMBERS = 128
MAX_GTFS_UNCOMPRESSED_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class GtfsFeedInspection:
    """Result of inspecting one possible GTFS static archive."""

    valid: bool
    members: tuple[str, ...]
    missing_required: tuple[str, ...]
    has_service_calendar: bool
    optional_members: tuple[str, ...]
    nested_directory: bool
    reason: str | None = None


def normalize_gtfs_member_name(name: str) -> str:
    """Return the case-insensitive basename used by the GTFS specification."""
    normalized = name.replace("\\", "/").strip("/")
    return PurePosixPath(normalized).name.casefold()


def inspect_gtfs_archive(payload: bytes) -> GtfsFeedInspection:
    """Validate a bounded ZIP payload using GTFS structural requirements.

    Detection intentionally relies on archive members rather than URL suffix or
    response content type. This supports extensionless feeds and endpoints named
    ``google_transit.zip``, ``gtfs-2.zip``, or simply ``/gtfs``.
    """
    if not payload:
        return _invalid("archive was empty")
    if len(payload) > MAX_GTFS_ARCHIVE_BYTES:
        return _invalid("archive exceeded the compressed-size limit")

    try:
        with ZipFile(BytesIO(payload)) as archive:
            infos = [item for item in archive.infolist() if not item.is_dir()]
            if len(infos) > MAX_GTFS_MEMBERS:
                return _invalid("archive contained too many members")
            if sum(item.file_size for item in infos) > MAX_GTFS_UNCOMPRESSED_BYTES:
                return _invalid("archive exceeded the uncompressed-size limit")

            normalized = tuple(
                sorted(
                    {
                        normalize_gtfs_member_name(item.filename)
                        for item in infos
                        if normalize_gtfs_member_name(item.filename)
                    }
                )
            )
            member_set = set(normalized)
            missing = tuple(sorted(GTFS_REQUIRED_FILES - member_set))
            service_calendar = bool(GTFS_SERVICE_FILES & member_set)
            optional = tuple(
                sorted((GTFS_OPTIONAL_FILES | GTFS_SERVICE_FILES) & member_set)
            )
            nested = any("/" in item.filename.replace("\\", "/").strip("/") for item in infos)

            if missing:
                return GtfsFeedInspection(
                    valid=False,
                    members=normalized,
                    missing_required=missing,
                    has_service_calendar=service_calendar,
                    optional_members=optional,
                    nested_directory=nested,
                    reason="archive did not contain the required GTFS tables",
                )
            if not service_calendar:
                return GtfsFeedInspection(
                    valid=False,
                    members=normalized,
                    missing_required=(),
                    has_service_calendar=False,
                    optional_members=optional,
                    nested_directory=nested,
                    reason="archive did not contain calendar.txt or calendar_dates.txt",
                )
            return GtfsFeedInspection(
                valid=True,
                members=normalized,
                missing_required=(),
                has_service_calendar=True,
                optional_members=optional,
                nested_directory=nested,
            )
    except BadZipFile:
        return _invalid("payload was not a ZIP archive")


def _invalid(reason: str) -> GtfsFeedInspection:
    return GtfsFeedInspection(
        valid=False,
        members=(),
        missing_required=tuple(sorted(GTFS_REQUIRED_FILES)),
        has_service_calendar=False,
        optional_members=(),
        nested_directory=False,
        reason=reason,
    )
