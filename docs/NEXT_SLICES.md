# Development slices

Only one implementation slice may be marked **In progress**. Completed work is retained for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001–S015 | Done | Intelligence Core | Provider-neutral structural inference, ranking, profiles, and descriptors exist and CI passes. |
| S016–S026 | Done | Knowledge Core | Aliases, observables, roles, locations, quality, summaries, explanations, fixtures, and capability negotiation exist and CI passes. |
| S027–S037 | Done | Planning Core | Stable entity and device plans, update and polling strategy, state, attributes, availability, naming, and diagnostics exist and CI passes. |
| S038–S044 | Done | Provider SDK | Contracts, registry, validation, mapping, failures, service orchestration, tests, and CI validation exist. |
| S045 | In progress | CKAN isolation | Inventory existing CKAN responsibilities, establish the intended package boundary, and identify every import or call path that must migrate without changing behavior. |
| S046 | Planned | CKAN adapter skeleton | A runtime-valid `ProviderAdapter` delegates to existing CKAN behavior; callers can resolve it through the provider registry. |
| S047 | Planned | CKAN discovery migration | CKAN search returns deterministic `DiscoveryPage` and `DatasetDescriptor` values with opaque pagination. |
| S048 | Planned | CKAN dataset and resource translation | Package and resource payloads are translated below the adapter boundary; CKAN JSON does not escape. |
| S049 | Planned | CKAN pipeline composition | Normalized descriptors feed profile, knowledge, and planning primitives through one pure integration path. |
| S050 | Planned | CKAN golden integration tests | Representative CKAN fixtures produce frozen, deterministic entity and device plans. |
| S051 | Planned | CKAN milestone validation | All accumulated tests pass; boundary leaks and regressions are corrected and validation evidence is recorded. |
| S052 | Planned | CSV adapter | Local or remote CSV metadata and rows enter the shared descriptor and planning pipeline. |
| S053 | Planned | JSON adapter | Common JSON record shapes enter the shared descriptor and planning pipeline. |
| S054 | Planned | Generic REST adapter | Constrained REST endpoints can be configured without provider-specific semantic logic. |
| S055 | Planned | Generic-provider validation | At least two non-CKAN source shapes validate the SDK and justify any shared contract changes. |
| S056+ | Planned | Portal adapters and HA materialization | Add portal families, then translate stable plans into native Home Assistant entities and devices. |

## S045 working checklist

- map current CKAN functions to client, translation, adapter, or provider-neutral ownership;
- identify modules importing `providers.ckan`;
- define compatibility exports needed during migration;
- avoid moving resource ranking or semantic inference into the CKAN package;
- specify tests that prove behavior preservation;
- update staged documentation before marking the slice complete.

## Selection rule

Reliability and concrete provider evidence take precedence over expansion. Do not add another provider-neutral framework while CKAN can still expose missing requirements through a smaller, testable change.

## Current decision

S045 is active. The immediate deliverable is an evidence-backed CKAN isolation map and migration boundary. Code movement begins only after that map identifies compatibility requirements and test coverage, reducing the chance of a broad, partially migrated state.
