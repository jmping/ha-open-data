"""Validate the bounded offline release-regression corpus."""

from __future__ import annotations

import json
from pathlib import Path


_ROOT = Path(__file__).parent
_CORPUS = _ROOT / "fixtures" / "release_corpus"
_REQUIRED_TOP_LEVEL = {"case_id", "source", "failure", "expected", "regression_tests"}


def test_release_corpus_cases_are_bounded_and_linked() -> None:
    """Every retained live failure must be reviewable and tied to real tests."""
    cases = sorted(_CORPUS.glob("*.json"))
    assert cases, "release corpus must contain at least one case"

    seen_ids: set[str] = set()
    for path in cases:
        assert path.stat().st_size <= 16 * 1024, f"{path.name} is not bounded"
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert _REQUIRED_TOP_LEVEL <= payload.keys()

        case_id = payload["case_id"]
        assert isinstance(case_id, str) and case_id
        assert case_id not in seen_ids
        seen_ids.add(case_id)

        source = payload["source"]
        assert isinstance(source, dict) and source.get("shape")
        assert isinstance(payload["failure"], str) and payload["failure"]
        assert isinstance(payload["expected"], dict) and payload["expected"]

        regression_tests = payload["regression_tests"]
        assert isinstance(regression_tests, list) and regression_tests
        for relative in regression_tests:
            target = _ROOT.parent / relative
            assert target.is_file(), f"{path.name} references missing test {relative}"

        serialized = path.read_text(encoding="utf-8").casefold()
        assert "password" not in serialized
        assert "authorization" not in serialized
        assert "api_key" not in serialized
