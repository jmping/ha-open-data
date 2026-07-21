"""Regression tests for the offline schema corpus tooling."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "schema_corpus.py"
SPEC = importlib.util.spec_from_file_location("schema_corpus", MODULE_PATH)
assert SPEC and SPEC.loader
schema_corpus = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = schema_corpus
SPEC.loader.exec_module(schema_corpus)


CorpusField = schema_corpus.CorpusField


def test_stable_corpus_id_ignores_portal_trailing_slash_and_case() -> None:
    first = schema_corpus.stable_corpus_id("HTTPS://DATA.EXAMPLE/", "CKAN", "abc")
    second = schema_corpus.stable_corpus_id("https://data.example", "ckan", "abc")
    assert first == second


def test_make_entry_bounds_samples_and_long_values() -> None:
    entry = schema_corpus.make_entry(
        portal_url="https://data.example/",
        provider="ckan",
        dataset_id="weather",
        title="Weather",
        fields=[CorpusField(name="temperature", label="Temperature", data_type="number")],
        sample_rows=[{"temperature": index, "note": "x" * 500} for index in range(20)],
    )
    assert entry.portal_url == "https://data.example"
    assert len(entry.sample_rows) == schema_corpus.MAX_SAMPLE_ROWS
    assert len(entry.sample_rows[0]["note"]) == schema_corpus.MAX_SAMPLE_VALUE_LENGTH


def test_make_entry_requires_fields() -> None:
    with pytest.raises(ValueError, match="at least one field"):
        schema_corpus.make_entry(
            portal_url="https://data.example",
            provider="ckan",
            dataset_id="empty",
            title="Empty",
            fields=[],
        )


def test_seed_corpus_is_valid_and_multilingual() -> None:
    path = Path(__file__).parent / "fixtures" / "schema_corpus" / "seed.json"
    entries = schema_corpus.load_corpus(path)
    summary = schema_corpus.summarize(entries)
    assert summary["entries"] == 4
    assert summary["providers"]["arcgis"] == 1
    assert {entry.language for entry in entries} >= {"en", "es", "ko", "th"}
    assert summary["unique_field_names"] >= 12


def test_normalize_field_name_preserves_non_latin_scripts() -> None:
    assert schema_corpus.normalize_field_name("측정 일시") == "측정_일시"
    assert schema_corpus.normalize_field_name("วันที่-ตรวจวัด") == "วันที่_ตรวจวัด"
