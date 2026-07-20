# Engineering log

This file records completed development slices, validation evidence, and follow-up work discovered during implementation.

## S001–S015 — Intelligence Core

Established deterministic CKAN resource selection, structural field inference, immutable dataset profiles, confidence and unit handling, identifier and geometry detection, dataset intelligence, generic resource ranking, and provider-neutral descriptors.

**Validation evidence:** GitHub Actions run `29761386815` completed successfully for commit `cdba84e788c6c80b5aead0eed0ab093f2042e9f1`.

## S016–S026 — Knowledge Core

Added canonical aliases, observable inference, dataset-role and location inference, quality scoring, summaries, explanation structures, fixture-backed golden profiles, and capability negotiation.

**Validation evidence:** GitHub Actions run `29762110068` completed successfully for commit `46af5ec405733b60f07bf6df0f7498d702ec5087`.

## S027–S037 — Planning Core

Added observable graphs, deterministic entity and device plans, update strategy, bounded polling heuristics, state and attribute selection, freshness-based availability, deterministic naming, and structured planning diagnostics.

`tests/test_planning_core.py` validates composition across these primitives without importing Home Assistant.

**Validation evidence:** GitHub Actions run `29762535146` completed successfully for commit `19fb23dda22bf42a144df123394f564c88870d4c`.

## S038–S044 — Provider SDK

Added immutable provider contexts, discovery requests and pages, a runtime-checkable adapter protocol, deterministic provider registration, structured failures, adapter validation, common metadata-to-descriptor mapping, and capability-aware provider service orchestration.

`tests/test_provider_sdk.py` covers the contracts and orchestration while preserving the accumulated legacy suite.

**Validation evidence:** GitHub Actions run `29763177537` completed successfully for commit `357306755ae09ad4a1ca561fb234c375c4e58be4`.

## Architecture decision — stop speculative core expansion

The Intelligence, Knowledge, Planning, and Provider SDK layers form the validated semantic platform. Additional provider-neutral execution, scheduling, or caching frameworks are deferred until multiple concrete providers demonstrate a shared requirement.

The next architectural test is moving CKAN behind the SDK. The desired outcome is not merely protocol conformance; it is that exactly one provider package understands CKAN payloads and all upper layers consume normalized descriptors or plans.

## S045 — CKAN isolation

**Status:** In progress.

This slice inventories the existing CKAN module, classifies each responsibility as client transport, payload translation, adapter orchestration, or provider-neutral behavior, and identifies compatibility exports and tests required for a mechanical migration.

Target boundary:

```text
providers/ckan/client.py       HTTP and CKAN actions
providers/ckan/translation.py  CKAN payloads to descriptors
providers/ckan/adapter.py      ProviderAdapter implementation
```

Resource ranking, structural inference, knowledge, and planning remain outside the provider package.

## Documentation transaction D001–D005

The repository documentation was inventoried and staged under `docs/proposed/`. `README.md`, `docs/PLAN.md`, `docs/ENGINEERING_LOG.md`, and `docs/NEXT_SLICES.md` were reconciled around the validated four-core architecture and the CKAN adoption program, then promoted together. `docs/proposed/MANIFEST.md` records the affected documents, invariants, and promotion result.

This process prevents canonical documents from describing mixed architectural states during multi-slice migrations.
