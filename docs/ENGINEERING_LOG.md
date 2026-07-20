# Engineering Log

This file records completed development slices, their validation evidence, and follow-up work discovered during implementation.

## Slice S001 — CKAN resource scoring

**Status:** Implemented; validation in progress

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

**Validation:**

- Focused unit tests added.
- Automated execution was initially unavailable because the repository had no active test workflow.

**Risks and follow-ups:**

- Real CKAN metadata varies across portals; fixtures from representative portals should be added later.
- Scoring diagnostics are internal only and are not yet exposed through Home Assistant diagnostics.

## Slice S002 — Automated test execution

**Status:** Implemented; awaiting first workflow result

**Goal:** Establish repeatable pull-request validation for the current pure-Python test suite.

**Files:**

- `.github/workflows/tests.yml`

**Behavior:**

- Runs `pytest` on pull requests and pushes to `main` using Python 3.12.
- Grants read-only repository permissions.

**Validation:**

- The workflow itself will be validated by its first GitHub Actions run.

**Risks and follow-ups:**

- The dependency installation is intentionally minimal. Home Assistant-specific tests may require a pinned development requirements file in a later slice.
