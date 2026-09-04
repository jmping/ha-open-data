"""Run bounded live audits against representative municipal open-data portals.

Third-party availability never gates normal CI. Reports capture which stage of the
real provider/analyzer/runtime pipeline succeeds or fails so repeatable findings can
become stable fixtures and generic fixes.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from custom_components.open_data.analyzer import analyze_dataset
from custom_components.open_data.failure_reporting import build_failure_report
from custom_components.open_data.field_roles import classify_field_roles
from custom_components.open_data.measure_freshness import build_measure_freshness_profiles
from custom_components.open_data.portal_inspector import (
    async_discover_catalog,
    async_inspect_portal,
)
from custom_components.open_data.temporal_policy import resolve_temporal_plan


SEARCH_QUERIES = ("weather", "air quality", "traffic", "water", "transit")

BATCHES = {
    1: (
        ("New York City", "https://data.cityofnewyork.us", "America/New_York"),
        ("Oklahoma City", "https://data.okc.gov", "America/Chicago"),
        ("London, Ontario", "https://opendata.london.ca", "America/Toronto"),
        ("Paris", "https://opendata.paris.fr", "Europe/Paris"),
        (
            "Barcelona",
            "https://opendata-ajuntament.barcelona.cat",
            "Europe/Madrid",
        ),
    ),
    2: (
        ("Chicago", "https://data.cityofchicago.org", "America/Chicago"),
        ("San Francisco", "https://data.sfgov.org", "America/Los_Angeles"),
        ("Austin", "https://data.austintexas.gov", "America/Chicago"),
        ("Seattle", "https://data.seattle.gov", "America/Los_Angeles"),
        ("Calgary", "https://data.calgary.ca", "America/Edmonton"),
    ),
    3: (
        ("Boston", "https://data.boston.gov", "America/New_York"),
        ("Montréal", "https://donnees.montreal.ca", "America/Toronto"),
        ("Toulouse", "https://data.toulouse-metropole.fr", "Europe/Paris"),
        ("Nantes", "https://data.nantesmetropole.fr", "Europe/Paris"),
        ("Raleigh", "https://data.raleighnc.gov", "America/New_York"),
    ),
    4: (
        ("Los Angeles", "https://data.lacity.org", "America/Los_Angeles"),
        ("Baltimore", "https://data.baltimorecity.gov", "America/New_York"),
        ("New Orleans", "https://data.nola.gov", "America/Chicago"),
        ("Edmonton", "https://data.edmonton.ca", "America/Edmonton"),
        ("Dallas", "https://www.dallasopendata.com", "America/Chicago"),
    ),
    5: (
        ("Washington, DC", "https://opendata.dc.gov", "America/New_York"),
        ("Ottawa", "https://open.ottawa.ca", "America/Toronto"),
        ("Vancouver", "https://opendata.vancouver.ca", "America/Vancouver"),
        (
            "Bordeaux",
            "https://opendata.bordeaux-metropole.fr",
            "Europe/Paris",
        ),
        ("Helsinki", "https://hri.fi/data/en_GB", "Europe/Helsinki"),
    ),
    6: (
        ("Madrid", "https://datos.madrid.es", "Europe/Madrid"),
        ("Milan", "https://dati.comune.milano.it", "Europe/Rome"),
        ("Berlin", "https://daten.berlin.de", "Europe/Berlin"),
        ("Zurich", "https://data.stadt-zuerich.ch", "Europe/Zurich"),
        ("Tokyo", "https://portal.data.metro.tokyo.lg.jp", "Asia/Tokyo"),
    ),
}


def _failure_context(
    result: dict[str, Any],
    *,
    provider: str | None,
    portal_url: str,
) -> dict[str, Any]:
    structure = result.get("structure") or {}
    return {
        "provider": provider,
        "portal_url": portal_url,
        "dataset_id": result.get("dataset_id"),
        "resource_id": result.get("resource_id"),
        "stage": result.get("stage"),
        "error_type": result.get("error_type"),
        "error_message": result.get("error"),
        "timestamp_fields": structure.get("timestamp_fields", []),
        "metric_fields": structure.get("metric_fields", []),
        "identity_fields": structure.get("identity_fields", []),
    }


async def _audit_dataset(
    provider: Any,
    dataset: Any,
    *,
    timezone_name: str,
    provider_name: str,
    portal_url: str,
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

        evidence_rows = rows
        if structure.metric_fields and structure.timestamp_fields:
            result["stage"] = "observation"
            observation_rows = await provider.async_observation_rows(
                resolved.dataset_id,
                resolved.resource_id,
                structure.timestamp_fields[0],
                limit=25,
            )
            result["observation_rows"] = len(observation_rows)
            if observation_rows:
                evidence_rows = observation_rows
            else:
                result["observation_warning"] = "bounded observation query returned no rows"

        result["stage"] = "freshness"
        freshness = build_measure_freshness_profiles(
            evidence_rows,
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
    except Exception as err:  # noqa: BLE001 - audit records every provider failure
        result["status"] = "fail"
        result["error_type"] = type(err).__name__
        result["error"] = str(err)[:500]
        result["failure_report"] = build_failure_report(
            _failure_context(
                result,
                provider=provider_name,
                portal_url=portal_url,
            )
        )
    return result


async def _targeted_candidates(provider: Any) -> tuple[list[Any], dict[str, Any]]:
    """Return deduplicated HA-relevant search candidates plus bounded evidence."""
    found: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    for query in SEARCH_QUERIES:
        try:
            matches = await provider.async_search_datasets(query, limit=3)
        except Exception as err:  # noqa: BLE001 - search failures are diagnostics
            evidence[query] = {"error_type": type(err).__name__, "error": str(err)[:200]}
            continue
        evidence[query] = [
            {"dataset_id": item.dataset_id, "title": item.title}
            for item in matches[:3]
        ]
        for item in matches:
            found.setdefault(item.dataset_id, item)
    return list(found.values()), evidence


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
        report["catalog_titles"] = [
            {"dataset_id": item.dataset_id, "title": item.title}
            for item in catalog[:30]
        ]
        targeted, search_evidence = await _targeted_candidates(inspected.provider)
        report["targeted_searches"] = search_evidence
    except Exception as err:  # noqa: BLE001
        report["status"] = "portal_failure"
        report["stage"] = "portal"
        report["error_type"] = type(err).__name__
        report["error"] = str(err)[:500]
        report["failure_report"] = build_failure_report(
            {
                "portal_url": portal_url,
                "stage": "portal",
                "error_type": type(err).__name__,
                "error_message": str(err)[:500],
            }
        )
        return report

    candidates: dict[str, Any] = {}
    for dataset in (*targeted, *catalog):
        candidates.setdefault(dataset.dataset_id, dataset)

    attempts = 0
    passes = 0
    for dataset in candidates.values():
        if attempts >= max(datasets_per_city * 5, 15):
            break
        audited = await _audit_dataset(
            inspected.provider,
            dataset,
            timezone_name=timezone_name,
            provider_name=inspected.description.provider,
            portal_url=inspected.description.portal_url,
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


async def _main(output: Path, datasets_per_city: int, batch: int) -> None:
    timeout = aiohttp.ClientTimeout(total=45)
    headers = {"User-Agent": "HAOpenDataImporter-live-audit/0.2"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        results = []
        for city, portal_url, timezone_name in BATCHES[batch]:
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

    passes = sum(item.get("status") == "pass" for item in results)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "bounded": True,
        "batch": batch,
        "city_count": len(results),
        "city_passes": passes,
        "city_failure_rate": round(1 - passes / max(len(results), 1), 3),
        "datasets_per_city_target": datasets_per_city,
        "search_queries": list(SEARCH_QUERIES),
        "portals": results,
    }
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("city-portal-results.json"))
    parser.add_argument("--datasets-per-city", type=int, default=3)
    parser.add_argument("--batch", type=int, choices=sorted(BATCHES), default=1)
    args = parser.parse_args()
    asyncio.run(
        _main(
            args.output,
            max(1, min(args.datasets_per_city, 5)),
            args.batch,
        )
    )
