# Development Slices

Only one slice may be marked **In progress**. Completed work is retained here for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001–S014 | Done | Intelligence core | Provider-neutral structural inference, ranking, and descriptors exist. |
| S015 | Done | Intelligence core validation | GitHub Actions run 29761386815 completed successfully. |
| S016–S025 | Done | Knowledge core | Aliases, observables, dataset roles, locations, quality, summaries, explanations, fixtures, and capabilities exist. |
| S026 | Done | Knowledge core validation | GitHub Actions run 29762110068 completed successfully. |
| S027 | Done | Observable graph | Observable relationships are grouped by logical source. |
| S028 | Done | Entity planning | Provider-neutral entity plans expose state sources and stable keys. |
| S029 | Done | Device planning | Entity plans group into deterministic logical devices. |
| S030 | Done | Update strategy | Snapshot, append-only, rolling-window, and historical modes have a shared model. |
| S031 | Done | Polling heuristics | Conservative bounded polling intervals are inferred from hints. |
| S032 | Done | State-field selection | The strongest observable is selected deterministically as entity state. |
| S033 | Done | Attribute selection | Non-state metadata is selected with stable exclusion and limits. |
| S034 | Done | Availability planning | Observation freshness maps to available, stale, or unknown states. |
| S035 | Done | Naming engine | Device and entity names are generated deterministically. |
| S036 | Done | Planning diagnostics | Planning decisions retain selections, reasons, and rejected alternatives. |
| S037 | In progress | Planning core validation | CI passes all accumulated planning-core and legacy tests; failures are corrected. |
| S038 | Planned | Planning orchestrator | Compose profile, knowledge, and planning primitives behind one pure entry point. |
| S039 | Planned | Property-based invariants | Add no-crash, deterministic-ordering, and bounded-confidence invariants. |

## Selection rule

Reliability work takes precedence over expansion. Provider adapter integration begins only after S037 is complete and the planning-core milestone is stable.

## Current decision

S037 is active. The planning core is implemented without Home Assistant imports; the next action is evidence-driven correction from GitHub Actions before adding an orchestrator or wiring providers.
