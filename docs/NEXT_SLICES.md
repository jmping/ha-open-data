# Development Slices

Only one slice may be marked **In progress**. Completed work is retained here for auditability and summarized in `ENGINEERING_LOG.md`.

| ID | Status | Slice | Exit criteria |
|---|---|---|---|
| S001–S014 | Done | Intelligence core | Provider-neutral structural inference, ranking, and descriptors exist. |
| S015 | Done | Intelligence core validation | GitHub Actions run 29761386815 completed successfully. |
| S016–S025 | Done | Knowledge core | Aliases, observables, dataset roles, locations, quality, summaries, explanations, fixtures, and capabilities exist. |
| S026 | Done | Knowledge core validation | GitHub Actions run 29762110068 completed successfully. |
| S027–S036 | Done | Planning core | Observable, entity, device, update, polling, state, attribute, availability, naming, and diagnostic plans exist. |
| S037 | Done | Planning core validation | GitHub Actions run 29762535146 completed successfully. |
| S038 | Done | Provider SDK contracts | Discovery requests, pages, contexts, and adapter protocol are provider-neutral. |
| S039 | Done | Provider registry | Adapters register and resolve through normalized stable identifiers. |
| S040 | Done | Provider failures | Provider errors have structured categories and retryability. |
| S041 | Done | Adapter validation | Adapter contracts are checked without network activity. |
| S042 | Done | Metadata mapping | Common provider metadata maps into shared dataset and resource descriptors. |
| S043 | Done | Provider service | Capability negotiation and adapter invocation share one orchestration boundary. |
| S044 | In progress | Provider SDK validation | CI passes all SDK, planning-core, and legacy tests; failures are corrected. |
| S045 | Planned | CKAN SDK adapter | Rework CKAN discovery and description behind the provider SDK contract. |
| S046 | Planned | CSV SDK adapter | Prove the SDK against a non-portal tabular source. |

## Selection rule

Concrete provider implementations now take precedence over additional provider-neutral abstraction. New shared layers require evidence from at least two adapters.

## Current decision

S044 is active. The provider SDK is implemented as pure Python and the next action is evidence-driven correction from GitHub Actions before adapting CKAN.
