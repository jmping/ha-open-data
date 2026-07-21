#!/usr/bin/env python3
"""Build and summarize a bounded, provider-independent schema corpus.

The corpus intentionally stores metadata, field definitions, and small redacted samples,
not complete source datasets.  Entries are stable JSON records suitable for ontology
regression tests and offline analysis.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

MAX_SAMPLE_ROWS = 5
MAX_SAMPLE_VALUE_LENGTH = 160


def normalize_field_name(value: str) -> str:
    """Return a conservative comparison key without discarding non-Latin text."""
    return re.sub(r"[^\w]+", "_", value.casefold(), flags=re.UNICODE).strip("_")


@dataclass(frozen=True, slots=True)
class CorpusField:
    name: str
    label: str
    data_type: str = "string"
    description: str | None = None


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    corpus_id: str
    portal_url: str
    provider: str
    dataset_id: str
    title: str
    language: str | None
    profile_hint: str | None
    fields: tuple[CorpusField, ...]
    sample_rows: tuple[dict[str, Any], ...] = ()


def stable_corpus_id(portal_url: str, provider: str, dataset_id: str) -> str:
    """Create a stable identifier that does not depend on dataset titles."""
    key = "\n".join((portal_url.rstrip("/").casefold(), provider.casefold(), dataset_id))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


def _bounded_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_SAMPLE_VALUE_LENGTH]
    if isinstance(value, list):
        return [_bounded_value(item) for item in value[:10]]
    if isinstance(value, dict):
        return {
            str(key)[:80]: _bounded_value(item)
            for key, item in list(value.items())[:20]
        }
    return str(value)[:MAX_SAMPLE_VALUE_LENGTH]


def make_entry(
    *,
    portal_url: str,
    provider: str,
    dataset_id: str,
    title: str,
    fields: Iterable[CorpusField],
    language: str | None = None,
    profile_hint: str | None = None,
    sample_rows: Iterable[dict[str, Any]] = (),
) -> CorpusEntry:
    """Normalize one source schema into a bounded corpus entry."""
    normalized_fields = tuple(fields)
    if not normalized_fields:
        raise ValueError("corpus entries require at least one field")
    bounded_rows = tuple(
        {str(key)[:120]: _bounded_value(value) for key, value in row.items()}
        for row in list(sample_rows)[:MAX_SAMPLE_ROWS]
    )
    return CorpusEntry(
        corpus_id=stable_corpus_id(portal_url, provider, dataset_id),
        portal_url=portal_url.rstrip("/"),
        provider=provider,
        dataset_id=dataset_id,
        title=title,
        language=language,
        profile_hint=profile_hint,
        fields=normalized_fields,
        sample_rows=bounded_rows,
    )


def load_corpus(path: Path) -> tuple[CorpusEntry, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries: list[CorpusEntry] = []
    for item in payload.get("entries", []):
        entries.append(
            CorpusEntry(
                **{key: value for key, value in item.items() if key not in {"fields", "sample_rows"}},
                fields=tuple(CorpusField(**field) for field in item["fields"]),
                sample_rows=tuple(item.get("sample_rows", [])),
            )
        )
    return tuple(entries)


def write_corpus(path: Path, entries: Iterable[CorpusEntry]) -> None:
    ordered = sorted(entries, key=lambda item: item.corpus_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"version": 1, "entries": [asdict(entry) for entry in ordered]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


def summarize(entries: Iterable[CorpusEntry]) -> dict[str, Any]:
    entries = tuple(entries)
    names = Counter(
        normalize_field_name(field.name)
        for entry in entries
        for field in entry.fields
    )
    return {
        "entries": len(entries),
        "portals": len({entry.portal_url for entry in entries}),
        "providers": dict(sorted(Counter(entry.provider for entry in entries).items())),
        "languages": dict(sorted(Counter(entry.language or "unknown" for entry in entries).items())),
        "profile_hints": dict(sorted(Counter(entry.profile_hint or "unknown" for entry in entries).items())),
        "unique_field_names": len(names),
        "common_field_names": names.most_common(50),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    entries = load_corpus(args.corpus)
    if args.summary:
        print(json.dumps(summarize(entries), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"validated {len(entries)} corpus entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
