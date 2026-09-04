"""Sample candidate open-data sources without building a global dataset registry.

The sampler is intentionally source-centric. It loads seed portals/agencies, normalizes
and deduplicates them, selects a deterministic daily slice, then runs bounded provider
inspection, catalog discovery, and topic searches. Output is an artifact/report only;
individual dataset IDs are evidence for that run and are not promoted into the seed
registry automatically.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from custom_components.open_data.portal_inspector import async_discover_catalog, async_inspect_portal


DEFAULT_TOPICS = (
    "weather",
    "air quality",
    "traffic",
    "transit",
    "water",
    "flood",
    "wildfire",
    "earthquake",
    "volcano",
    "outage",
)


@dataclass(frozen=True, slots=True)
class SeedSource:
    name: str
    url: str
    provenance: str
    source_type: str = "unknown"
    region_hint: str = ""
    language_hint: str = ""


def _canonical_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    scheme = parsed.scheme.lower() or "https"
    host = (parsed.hostname or "").lower()
    if not host:
        return ""
    port = f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
    path = parsed.path.rstrip("/")
    return urlunsplit((scheme, host + port, path, "", ""))


def _load_csv(path: Path) -> Iterable[SeedSource]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized = {str(key).strip().casefold(): (value or "").strip() for key, value in row.items()}
            url = normalized.get("url") or normalized.get("portal") or normalized.get("website") or ""
            name = normalized.get("name") or normalized.get("portal name") or normalized.get("title") or url
            source_type = normalized.get("type") or normalized.get("source type") or normalized.get("level") or "unknown"
            region_hint = normalized.get("region") or normalized.get("location") or normalized.get("country") or ""
            language_hint = normalized.get("language") or ""
            canonical = _canonical_url(url)
            if canonical:
                yield SeedSource(
                    name=name or canonical,
                    url=canonical,
                    provenance=path.name,
                    source_type=source_type,
                    region_hint=region_hint,
                    language_hint=language_hint,
                )


def _load_json(path: Path) -> Iterable[SeedSource]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("sources", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return ()
    sources: list[SeedSource] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        url = _canonical_url(str(item.get("url") or item.get("portal_url") or ""))
        if not url:
            continue
        sources.append(
            SeedSource(
                name=str(item.get("name") or item.get("title") or url),
                url=url,
                provenance=str(item.get("provenance") or path.name),
                source_type=str(item.get("source_type") or item.get("type") or "unknown"),
                region_hint=str(item.get("region_hint") or item.get("region") or ""),
                language_hint=str(item.get("language_hint") or item.get("language") or ""),
            )
        )
    return sources


def load_sources(paths: Iterable[Path]) -> list[SeedSource]:
    deduped: dict[str, SeedSource] = {}
    for path in paths:
        if not path.exists():
            continue
        rows = _load_csv(path) if path.suffix.casefold() == ".csv" else _load_json(path)
        for source in rows:
            deduped.setdefault(source.url, source)
    return sorted(deduped.values(), key=lambda item: (item.url, item.name.casefold()))


def select_daily_sources(sources: list[SeedSource], *, sample_size: int, day: date) -> list[SeedSource]:
    if not sources or sample_size <= 0:
        return []
    day_key = day.isoformat()
    ranked = sorted(
        sources,
        key=lambda source: hashlib.sha256(f"{day_key}|{source.url}".encode()).digest(),
    )
    return ranked[: min(sample_size, len(ranked))]


async def _search_topics(provider: Any, topics: tuple[str, ...]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for topic in topics:
        try:
            matches = await provider.async_search_datasets(topic, limit=3)
            evidence[topic] = [
                {"title": item.title, "dataset_id": item.dataset_id}
                for item in matches[:3]
            ]
        except Exception as err:  # noqa: BLE001 - diagnostic sampler
            evidence[topic] = {"error_type": type(err).__name__, "error": str(err)[:240]}
    return evidence


async def audit_source(
    session: aiohttp.ClientSession,
    source: SeedSource,
    *,
    topics: tuple[str, ...],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": source.name,
        "seed_url": source.url,
        "provenance": source.provenance,
        "source_type": source.source_type,
        "region_hint": source.region_hint,
        "language_hint": source.language_hint,
    }
    try:
        inspected = await async_inspect_portal(session, source.url)
        result.update(
            {
                "status": "recognized",
                "provider": inspected.description.provider,
                "resolved_url": inspected.description.portal_url,
                "capabilities": inspected.description.capabilities,
            }
        )
        catalog, errors = await async_discover_catalog(inspected, limit=20)
        result["catalog_sample_size"] = len(catalog)
        result["catalog_errors"] = errors
        result["catalog_sample"] = [
            {"title": item.title, "dataset_id": item.dataset_id}
            for item in catalog[:20]
        ]
        result["topic_searches"] = await _search_topics(inspected.provider, topics)
        result["observed_topic_hits"] = sorted(
            topic
            for topic, value in result["topic_searches"].items()
            if isinstance(value, list) and value
        )
    except Exception as err:  # noqa: BLE001 - report unrecognized/dead sources
        result.update(
            {
                "status": "unrecognized_or_failed",
                "error_type": type(err).__name__,
                "error": str(err)[:500],
            }
        )
    return result


async def _main(args: argparse.Namespace) -> None:
    sources = load_sources(tuple(args.seed))
    selected = select_daily_sources(
        sources,
        sample_size=max(1, min(args.sample_size, 200)),
        day=date.fromisoformat(args.day),
    )
    timeout = aiohttp.ClientTimeout(total=args.timeout)
    headers = {"User-Agent": "HAOpenDataImporter-source-sampler/0.2"}
    semaphore = asyncio.Semaphore(max(1, min(args.concurrency, 10)))

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async def _run(source: SeedSource) -> dict[str, Any]:
            async with semaphore:
                return await audit_source(session, source, topics=tuple(args.topic))

        results = await asyncio.gather(*(_run(source) for source in selected))

    recognized = sum(item.get("status") == "recognized" for item in results)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "day": args.day,
        "seed_source_count": len(sources),
        "sample_size": len(results),
        "recognized_sources": recognized,
        "recognition_rate": round(recognized / max(len(results), 1), 3),
        "topics": list(args.topic),
        "source_centric": True,
        "datasets_are_run_evidence_only": True,
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, action="append", required=True)
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--day", default=date.today().isoformat())
    parser.add_argument("--topic", action="append", default=list(DEFAULT_TOPICS))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("source-sample-results.json"))
    asyncio.run(_main(parser.parse_args()))
