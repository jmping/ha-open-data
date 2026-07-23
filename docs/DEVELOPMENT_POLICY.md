# Development and pull-request reconciliation policy

This project must not begin substantial implementation work without first checking active pull requests and branches for overlapping or incompatible work.

## Required pre-work check

Before creating a new feature branch or making a cross-cutting architectural change, the implementer must:

1. List every open pull request against `main`, including drafts.
2. Search open pull-request titles, bodies, changed filenames, and relevant issue threads for overlap with the proposed work.
3. Compare the intended change with current `main` and any overlapping pull-request heads.
4. Record one of these dispositions for each overlapping PR:
   - **incorporate** — build on or complete the existing PR;
   - **extract** — salvage a bounded feature into a fresh PR;
   - **supersede** — document why the existing implementation is obsolete;
   - **defer** — leave it open with a named dependency or unresolved decision.
5. Link the new work to the existing PR or issue and state which behavior is preserved, replaced, or intentionally omitted.

Implementation must pause for clarification when two branches encode materially different product behavior and the intended behavior cannot be inferred from existing issues or user direction.

## Feature-accounting requirement

Every substantial PR must contain a feature-accounting section with:

- requested behavior;
- behavior implemented;
- behavior intentionally deferred;
- existing PRs or branches reviewed;
- compatibility or migration impact;
- tests proving the retained behavior.

A PR must not be described as complete when requested behavior only exists on another unmerged branch.

## Merge and closure rules

- Do not merge old, heavily diverged branches wholesale merely to recover features.
- Extract independently testable behavior into small PRs against current `main`.
- Do not close a superseded PR until its useful behavior has been either merged, explicitly rejected, or recorded in a tracking issue.
- When closing a superseded PR, leave a final comment listing:
  - features retained and where they landed;
  - features rejected and why;
  - features still outstanding and their tracking issue.
- Draft PRs count as active work and must be included in reconciliation.

## Architecture-change gate

Changes to provider contracts, config-entry ownership, dataset analysis, observation identity, polling, history retrieval, or entity construction require an explicit compatibility review against all open PRs touching those areas.

The review should prefer one current architecture rather than maintaining parallel frameworks. New abstractions must replace or simplify existing ones, not silently coexist with incompatible models.

## Ongoing repository hygiene

At least once per development cycle:

1. review all open PRs;
2. update stale PR descriptions with current status;
3. close branches that have a complete salvage record;
4. update the tracking issue for unfinished requested features;
5. verify that `main` contains the behavior described as shipped.

## Current recovery process

Issue #26 is the authoritative record for reconciling PRs #1, #2, and #7 with current `main`. Those PRs are feature sources, not direct merge candidates. Each retained feature must land through a small current-base PR with regression coverage before the old PR is closed.
