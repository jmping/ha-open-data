# Engineering Log

This file records completed development slices, validation evidence, and follow-up work discovered during implementation.

## S001–S015 — Intelligence core

The first milestone established deterministic CKAN resource selection, structural field inference, dataset profiles, confidence and unit handling, identifier and geometry detection, dataset intelligence, generic resource ranking, and provider-neutral descriptors.

**Validation evidence:** GitHub Actions run `29761386815` completed successfully for commit `cdba84e788c6c80b5aead0eed0ab093f2042e9f1`.

## S016–S026 — Knowledge core

The second milestone added canonical aliases, observable inference, dataset-role and location inference, quality scoring, summaries, explanation graphs, fixture-backed golden profiles, and capability negotiation.

**Validation evidence:** GitHub Actions run `29762110068` completed successfully for commit `46af5ec405733b60f07bf6df0f7498d702ec5087`.

## S027–S037 — Planning core

The third milestone added observable graphs, immutable entity and device plans, update strategies, polling heuristics, state and attribute selection, availability planning, deterministic naming, and structured planning diagnostics.

**Validation evidence:** GitHub Actions run `29762535146` completed successfully for commit `19fb23dda22bf42a144df123394f564c88870d4c`.

## S038 — Provider SDK contracts

Introduces immutable provider context, discovery request and page models, and a runtime-checkable adapter protocol covering discovery and dataset description.

## S039 — Provider registry

Registers adapters under normalized stable identifiers, rejects duplicate registrations, and exposes deterministic provider ordering.

## S040 — Provider failures

Defines structured provider failure categories, retryability, and a single exception wrapper suitable for diagnostics and integration boundaries.

## S041 — Adapter validation

Checks provider identity, capabilities, discovery, and description methods without performing network calls.

## S042 — Metadata mapping

Maps common provider metadata shapes into shared dataset and resource descriptors while enforcing stable identity and required titles.

## S043 — Provider service

Combines registry resolution, adapter validation, capability negotiation, and discovery invocation behind one provider-neutral service boundary.

## S044 — Provider SDK validation

**Status:** In progress.

`tests/test_provider_sdk.py` covers adapter registration, request validation, metadata mapping, contract validation, capability negotiation, structured unsupported failures, and asynchronous discovery invocation. The current branch head must complete GitHub Actions successfully before CKAN is moved behind the SDK.
