#!/usr/bin/env python3
"""Download and structurally inspect the GTFS feed regression corpus.

This is intentionally an opt-in/live test: public feed URLs frequently move, reject
HEAD requests, require redirects, or temporarily fail. Unit tests cover deterministic
archive validation; this script records current endpoint behavior without making the
normal test suite depend on third-party uptime.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from custom_components.open_data.feeds.gtfs import (
    MAX_GTFS_ARCHIVE_BYTES,
    inspect_gtfs_archive,
)

FEEDS: tuple[tuple[str, str], ...] = (
    ("caltrain-trillium", "https://data.trilliumtransit.com/gtfs/caltrain-ca-us/caltrain-ca-us.zip"),
    ("caltrain-legacy", "http://www.caltrain.com/Assets/GTFS/caltrain/CT-GTFS.zip"),
    ("mta-s3", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip"),
    ("mta-legacy", "http://web.mta.info/developers/data/nyct/subway/google_transit.zip"),
    ("path-transitland", "http://gtfs-source-feeds.transit.land/path-nj-us.zip"),
    ("path-github", "https://github.com/transitland/gtfs-archives-not-hosted-elsewhere/raw/master/path-nj-us.zip"),
    ("path-trillium", "https://data.trilliumtransit.com/gtfs/path-nj-us/path-nj-us.zip"),
    ("cdmx", "https://datos.cdmx.gob.mx/dataset/75538d96-3ade-4bc5-ae7d-d85595e4522d/resource/32ed1b6b-41cd-49b3-b7f0-b57acb0eb819/download/gtfs-2.zip"),
    ("trimet", "http://developer.trimet.org/schedule/gtfs.zip"),
    ("chapel-hill-direct", "http://mychtransit.org/gtfs"),
    ("chapel-hill-trillium", "https://data.trilliumtransit.com/gtfs/chapel-hill-transit-nc-us/chapel-hill-transit-nc-us.zip"),
    ("kern-transit", "https://data.trilliumtransit.com/gtfs/kerncounty-ca-us/kerncounty-ca-us.zip"),
)


def _download(url: str, timeout: float) -> tuple[bytes, str, str | None]:
    request = Request(
        url,
        headers={
            "Accept": "application/zip, application/octet-stream, */*",
            "User-Agent": "HAOpenDataImporter GTFS regression check",
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed corpus
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type")
        announced = response.headers.get("Content-Length")
        if announced is not None and int(announced) > MAX_GTFS_ARCHIVE_BYTES:
            raise ValueError("compressed response exceeded the GTFS size limit")
        payload = response.read(MAX_GTFS_ARCHIVE_BYTES + 1)
        if len(payload) > MAX_GTFS_ARCHIVE_BYTES:
            raise ValueError("compressed response exceeded the GTFS size limit")
        return payload, final_url, content_type


def inspect_live_feed(name: str, url: str, timeout: float) -> dict[str, object]:
    result: dict[str, object] = {"name": name, "url": url}
    try:
        payload, final_url, content_type = _download(url, timeout)
        inspection = inspect_gtfs_archive(payload)
        result.update(
            {
                "reachable": True,
                "final_url": final_url,
                "content_type": content_type,
                "bytes": len(payload),
                "inspection": asdict(inspection),
            }
        )
    except HTTPError as err:
        result.update({"reachable": False, "http_status": err.code, "error": str(err)})
    except (URLError, TimeoutError, ValueError, OSError) as err:
        result.update({"reachable": False, "error": str(err)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--strict", action="store_true", help="fail if any URL is unavailable or invalid")
    parser.add_argument("--output", help="optional JSON output path")
    args = parser.parse_args()

    results = [inspect_live_feed(name, url, args.timeout) for name, url in FEEDS]
    document = {"feeds": results}
    rendered = json.dumps(document, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            output.write(rendered)
            output.write("\n")

    valid = sum(
        bool(item.get("inspection", {}).get("valid"))
        for item in results
        if isinstance(item.get("inspection"), dict)
    )
    failures = len(results) - valid
    print(f"GTFS live corpus: {valid} valid, {failures} unavailable or invalid", file=sys.stderr)
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
