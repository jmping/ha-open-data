# Development Slices

Only one slice may be marked **In progress**. Completed work is retained here for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001 | Done | CKAN resource scoring | Automatic selection is deterministic, explicit selection is preserved, and focused tests exist. |
| S002 | Validation | Automated test execution | The corrected pull-request workflow completes successfully. |
| S003 | Done | Resource scoring robustness | Mixed CKAN metadata is handled deterministically with focused regression tests. |
| S004 | Done | Timestamp field detection | A pure helper ranks likely timestamp fields with deterministic tests and no provider coupling. |
| S005 | In progress | Coordinate field detection | Pure helpers identify latitude/longitude pairs and reject common false positives. |
| S006 | Planned | Field semantic classification | Pure field-name/type classification composes timestamp and coordinate signals. |
| S007 | Planned | Dataset profile model | A small immutable profile composes inferred field semantics without changing provider behavior. |
| S008 | Planned | CKAN profile integration | CKAN metadata produces a dataset profile at one integration point with diagnostics coverage. |

## Selection rule

The next slice is chosen by reducing the largest current reliability risk before expanding functionality. A new provider or broad semantic layer begins a new milestone and is outside this backlog.

## Current decision

S005 is active. Timestamp and coordinate detection should exist as tested, independent primitives before S006 composes them into field semantics. S002 remains under validation and takes precedence if the corrected workflow reports another failure.
