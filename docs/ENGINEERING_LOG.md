# Engineering Log

This file records completed development slices, validation evidence, and follow-up work discovered during implementation.

## S001–S015 — Intelligence core

The first milestone established deterministic CKAN resource selection, structural field inference, dataset profiles, confidence and unit handling, identifier and geometry detection, dataset intelligence, generic resource ranking, and provider-neutral descriptors.

**Validation evidence:** GitHub Actions run `29761386815` completed successfully for commit `cdba84e788c6c80b5aead0eed0ab093f2042e9f1`.

## S016–S026 — Knowledge core

The second milestone added canonical aliases, observable inference, dataset-role and location inference, quality scoring, summaries, explanation graphs, fixture-backed golden profiles, and capability negotiation.

**Validation evidence:** GitHub Actions run `29762110068` completed successfully for commit `46af5ec405733b60f07bf6df0f7498d702ec5087`.

## S027 — Observable graph

Groups inferred observables by logical source while preserving stable source and field ordering.

## S028 — Entity planning

Creates immutable provider-neutral entity plans with stable keys, state fields, observable kinds, units, and attribute slots.

## S029 — Device planning

Groups entity plans into deterministic logical devices without importing Home Assistant.

## S030 — Update strategy

Represents snapshot, append-only, rolling-window, and historical update modes and conservatively infers a strategy from temporal and observation signals.

## S031 — Polling heuristics

Produces bounded polling intervals from declared cadence, live-data hints, and temporal structure.

## S032 — State-field selection

Selects the highest-confidence observable as entity state with deterministic semantic and field-name tie-breaking.

## S033 — Attribute selection

Selects deduplicated non-state fields while honoring exclusions and bounded attribute counts.

## S034 — Availability planning

Classifies observations as available, stale, or unknown using a poll-derived staleness window and timezone-safe timestamps.

## S035 — Naming engine

Generates deterministic device and entity display names from dataset, location, and observable semantics.

## S036 — Planning diagnostics

Captures selected values, reasons, and rejected alternatives in a shared immutable diagnostics model.

## S037 — Planning core validation

**Status:** In progress.

`tests/test_planning_core.py` covers composition across observable graphs, entity and device plans, update and polling strategy, state and attribute selection, availability, naming, and diagnostics. The current branch head must complete GitHub Actions successfully before this milestone is recorded as stable.
