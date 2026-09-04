"""Run a bounded live audit against representative municipal open-data portals.

This is intentionally non-authoritative: third-party availability must not gate
normal CI. The report captures which stage of the real provider/analyzer pipeline
succeeds or fails so stable fixtures can be derived from repeatable findings.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from custom_components.open_data.analyzer import analyze_dataset
from custom_components.open_data.field_roles import classify_field_roles
from custom_components.open_data.measure_freshness import build_measure_freshness_profiles
from custom_components.open_data.portal_inspector import async_discover_catalog, async_inspect_portal
from custom_components.open_data.temporal_policy import resolve_temporal_plan


PORTALS = (
    ("New York City", "https://data.cityofnewyork.us", "America/New_York"),
    ("Oklahoma City", "https://data.okc.gov", "America/Chicago"),
    ("London, Ontario", "https://opendata.london.ca", "America/Toronto"),
    ("Paris", "https://opendata.paris.fr", "Europe/Paris"),
    (
        "Barcelona",
        "https://opendata-ajuntament.barcelona.cat",
        "Europe/Madrid",
    ),
)


async def _audit_dataset(
    provider: Any,
    dataset: Any,
    *,
    timezone_name: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "dataset_id": dataset.dataset_id,
        "title": dataset.title,
        "resource_id": dataset.resource_id,
        "stage": "metadata",
    }
    try:
        resolved = await provider.async_get_dataset(dataset.dataset_id, dataset.resource_id)
        result["field_count"] = len(resolved.fields)
        result["stage"] = "sample"
        rows = await provider.async_sample_rows(
            resolved.dataset_id, resolved.resource_id, limit=40
        )
        result["sample_rows"] = len(rows)
        if not rows:
            result["status"] = "empty_sample"
            return result

        result["stage"] = "analysis"
        structure = analyze_dataset(resolved, rows)
        roles = classify_field_roles(resolved, structure)
        result["structure"] = {
            "kind": structure.kind,
            "identity_fields": list(structure.identity_fields),
            "display_fields": list(structure.display_fields),
            "timestamp_fields": list(structure.timestamp_fields),
            "metric_fields": list(structure.metric_fields),
            "location_fields": list(structure.location_fields),
        }
        result["role_counts"] = {
            role: sum(value == role for value in roles.values())
            for role in sorted(set(roles.values()))
        }

        result["stage"] = "temporal"
        temporal = resolve_temporal_plan(
            tuple(field.name for field in resolved.fields),
            rows,
            home_assistant_timezone=timezone_name,
            now=datetime.now(ZoneInfo(timezone_name)),
        )
        result["temporal"] = temporal.as_dict()

        result["stage"] = "freshness"
        freshness = build_measure_freshness_profiles(
            rows,
            metric_fields=structure.metric_fields,
            timestamp_fields=structure.timestamp_fields,
            timezone_name=timezone_name,
            now=datetime.now(ZoneInfo(timezone_name)),
        )
        result["freshness"] = {
            field: {
                "status": profile.status,
                "auto_import": profile.auto_import,
                "latest_observation_at": profile.latest_observation_at,
                "cadence_seconds": profile.cadence_seconds,
                "presentation": profile.presentation,
            }
            for field, profile in freshness.items()
        }
        result["status"] = "pass"
        result["stage"] = "complete"
    except Exception as err:  # noqa: BLE001 - audit must report every provider failure
        result["status"] = "fail"
        result["error_type"] = type(err).__name__
        result["error"] = str(err)[:500]
    return result


async def _audit_portal(
    session: aiohttp.ClientSession,
    city: str,
    portal_url: str,
    timezone_name: str,
    *,
    datasets_per_city: int,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "city": city,
        "requested_portal_url": portal_url,
        "timezone": timezone_name,
        "datasets": [],
    }
    try:
        inspected = await async_inspect_portal(session, portal_url)
        report["provider"] = inspected.description.provider
        report["resolved_portal_url"] = inspected.description.portal_url
        report["capabilities"] = inspected.description.capabilities
        catalog, catalog_errors = await async_discover_catalog(inspected, limit=30)
        report["catalog_size_sampled"] = len(catalog)
        report["catalog_errors"] = catalog_errors
    except Exception as err:  # noqa: BLE001
        report["status"] = "portal_failure"
        report["error_type"] = type(err).__name__
        report["error"] = str(err)[:500]
        return report

    # Try enough catalog candidates to obtain several actual row-level audits while
    # retaining failures. This catches resources that are discoverable but not
    # queryable instead of silently skipping them.
    attempts = 0
    passes = 0
    for dataset in catalog:
        if attempts >= max(datasets_per_city * 4, datasets_per_city):
            break
        audited = await _audit_dataset(
            inspected.provider, dataset, timezone_name=timezone_name
        )
        report["datasets"].append(audited)
        attempts += 1
        if audited.get("status") == "pass":
            passes += 1
        if passes >= datasets_per_city and attempts >= datasets_per_city:
            break

    report["status"] = "pass" if passes else "no_queryable_samples"
    report["dataset_passes"] = passes
    report["dataset_attempts"] = attempts
    return report


async def _main(output: Path, datasets_per_city: int) -> None:
    timeout = aiohttp.ClientTimeout(total=45)
    headers = {"User-Agent": "HAOpenDataImporter-live-audit/0.2"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        results = []
        for city, portal_url, timezone_name in PORTALS:
            print(f"Auditing {city}: {portal_url}", flush=True)
            result = await _audit_portal(
                session,
                city,
                portal_url,
                timezone_name,
                datasets_per_city=datasets_per_city,
            )
            results.append(result)
            print(
                f"  {result.get('provider', 'unknown')}: {result.get('status')}",
                flush=True,
            )

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "bounded": True,
        "datasets_per_city_target": datasets_per_city,
        "portals": results,
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("city-portal-results.json"))
    parser.add_argument("--datasets-per-city", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(_main(args.output, max(1, min(args.datasets_per_city, 5))))
