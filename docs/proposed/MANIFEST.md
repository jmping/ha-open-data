# Documentation transaction manifest

## Purpose

This directory stages a coherent documentation set for the provider-SDK adoption program. Canonical documents are promoted only after every staged document agrees on architecture, slice numbering, validation evidence, and next work.

## Inventory

| Canonical document | Staged mirror | Role | Required changes |
|---|---|---|---|
| `README.md` | `docs/proposed/README.md` | Public project overview | Replace the legacy provider/coordinator picture with the validated Intelligence, Knowledge, Planning, and Provider SDK architecture; describe CKAN migration as current work. |
| `docs/PLAN.md` | `docs/proposed/PLAN.md` | Long-range architecture and delivery plan | Replace the obsolete Socrata-first plan with a provider-neutral plan and concrete CKAN adoption slices. |
| `docs/ENGINEERING_LOG.md` | `docs/proposed/ENGINEERING_LOG.md` | Completed work and evidence | Record successful Planning and Provider SDK validation and the documentation transaction. |
| `docs/NEXT_SLICES.md` | `docs/proposed/NEXT_SLICES.md` | Active execution queue | Mark S044 complete and define S045–S051 as the CKAN SDK adoption sequence. |

## Transaction slices

| Slice | Status | Work |
|---|---|---|
| D001 | Done | Inventory canonical architecture and roadmap documents. |
| D002 | Done | Create staged mirrors without changing canonical documents. |
| D003 | Done | Reconcile terminology, milestones, validation evidence, and slice numbering across mirrors. |
| D004 | Done | Validate that all mirrors describe the same dependency direction and active slice. |
| D005 | Done | Promote the staged documents to their canonical paths. |

## Cross-document invariants

- The validated semantic platform consists of Intelligence, Knowledge, Planning, and Provider SDK cores.
- GitHub Actions runs `29761386815`, `29762110068`, `29762535146`, and `29763177537` are recorded as successful.
- No document claims that Home Assistant materialization is complete.
- CKAN is the first adapter used to validate the Provider SDK.
- S045 is the first active CKAN migration slice.
- Provider-specific JSON must not cross the adapter boundary.
- New abstractions are extracted only from concrete cross-provider pressure.

## Promotion result

The mirrors were promoted as one documentation transaction. This manifest remains as the audit record and checklist for future staged documentation changes.
