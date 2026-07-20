# Engineering Log

This file records completed development slices, validation evidence, and follow-up work discovered during implementation.

## Slice S001 — CKAN resource scoring

**Status:** Implemented; validation pending

**Goal:** Replace first-match CKAN resource selection with deterministic, explainable scoring while preserving explicit resource selection.

**Files:**

- `custom_components/open_data/providers/resource_scoring.py`
- `custom_components/open_data/providers/ckan.py`
- `tests/test_resource_scoring.py`

**Behavior:**

- Rejects resources that are not active DataStore resources.
- Prefers structured tabular formats.
- Uses resource modification time as a secondary ranking signal.
- Preserves source order as the final stable tie-breaker.
- Leaves explicit `resource_id` validation unchanged.

## Slice S002 — Automated test execution

**Status:** Corrected; awaiting rerun

**Goal:** Establish repeatable pull-request validation.

**Change record:**

- Added `.github/workflows/tests.yml` for Python 3.12 and `pytest`.
- The first run reached test execution but failed because importing the integration requires Home Assistant.
- Updated the workflow to install `homeassistant` with the test dependencies.

**Validation evidence:** GitHub Actions run 29760441005 failed at the `Run tests` step after checkout, Python setup, and dependency installation succeeded. The corrective commit is awaiting a new run.

## Slice S003 — Resource scoring robustness

**Status:** Implemented; validation pending

**Goal:** Safely handle mixed real-world CKAN metadata without nondeterministic time behavior.

**Behavior:**

- Accepts mapping objects rather than requiring concrete dictionaries.
- Recognizes common MIME-style format values.
- Falls back through multiple modification timestamps when earlier values are malformed.
- Normalizes naive and offset timestamps to UTC.
- Treats a null state as CKAN's default active state.

**Tests:** Added coverage for MIME formats, malformed timestamp fallback, UTC normalization, and null state values.

## Slice S004 — Timestamp field detection

**Status:** Implemented; validation pending

**Goal:** Add a provider-neutral, deterministic timestamp candidate ranker.

**Files:**

- `custom_components/open_data/timestamp_detection.py`
- `tests/test_timestamp_detection.py`

**Behavior:**

- Scores temporal data types, strong field names, human-readable labels, and observation timing tokens.
- Rejects timezone, UTC-offset, and duration false positives.
- Uses stable field-name ordering for equal scores.

**Next assessment:** Coordinate detection is the best next slice because it completes the two foundational structural signals needed before a broader field classifier can compose semantics.
