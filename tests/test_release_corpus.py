"""Validate the bounded release-regression corpus."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).parent
_CORPUS = _ROOT / "fixtures" / "release_corpus"
_MAX_CASE_BYTES = 32 * 1024
_MAX_FIELDS = 64
_MAX_ROWS = 12
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "client_secret",
    "password",
    "secret",
    "token",
}


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).casefold())
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def test_release_corpus_is_bounded_redacted_and_linked() -> None:
    paths = sorted(_CORPUS.glob("*.json"))
    assert paths, "release corpus must retain at least one regression case"

    case_ids: set[str] = set()
    for path in paths:
        raw = path.read_bytes()
        assert len(raw) <= _MAX_CASE_BYTES, f"{path.name} exceeds bounded case size"
        case = json.loads(raw)

        assert set(case) == {
            "case_id",
            "source",
            "failure",
            "schema",
            "sample_rows",
            "expected",
            "redaction",
        }
        case_id = case["case_id"]
        assert isinstance(case_id, str) and case_id
        assert case_id not in case_ids, f"duplicate release case id: {case_id}"
        case_ids.add(case_id)

        source = case["source"]
        assert source["portal_url"].startswith(("http://", "https://"))
        assert source["provider"]
        assert source["structure"]
        assert source["live_validated_at"]

        assert len(case["schema"]) <= _MAX_FIELDS
        assert len(case["sample_rows"]) <= _MAX_ROWS
        assert case["redaction"]["bounded"] is True
        assert case["redaction"]["contains_personal_data"] is False
        assert not (_walk_keys(case) & _SENSITIVE_KEYS)

        node_id = case["failure"]["regression_test"]
        test_path = _ROOT.parent / node_id.split("::", 1)[0]
        assert test_path.is_file(), f"missing regression test for {case_id}: {node_id}"


def test_release_corpus_samples_use_only_declared_fields() -> None:
    for path in sorted(_CORPUS.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        declared = {field["name"] for field in case["schema"]}
        for row in case["sample_rows"]:
            assert set(row) <= declared, f"{path.name} contains undeclared sample fields"
