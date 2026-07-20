# Development Slices

Only one slice may be marked **In progress**. Completed work is retained here for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001 | Done | CKAN resource scoring | Automatic selection is deterministic, explicit selection is preserved, and focused tests exist. |
| S002 | In progress | Automated test execution | The pull-request workflow runs the test suite successfully, or failures are diagnosed and corrected. |
| S003 | Planned | Resource scoring robustness | Scoring accepts malformed and mixed CKAN metadata without exceptions; representative fixtures cover the behavior. |
| S004 | Planned | Timestamp field detection | A pure helper ranks likely timestamp fields with deterministic tests and no provider coupling. |
| S005 | Planned | Coordinate field detection | Pure helpers identify latitude/longitude pairs and reject common false positives. |
| S006 | Planned | Field semantic classification | Pure field-name/type classification composes timestamp and coordinate signals. |
| S007 | Planned | Dataset profile model | A small immutable profile composes inferred field semantics without changing provider behavior. |
| S008 | Planned | CKAN profile integration | CKAN metadata produces a dataset profile at one integration point with diagnostics coverage. |

## Selection rule

The next slice is chosen by reducing the largest current reliability risk before expanding functionality. A new provider or broad semantic layer begins a new milestone and is outside this backlog.

## Current decision

S002 is active because further slices cannot be called stable until automated validation evidence exists.
