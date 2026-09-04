# Open Data for Home Assistant

A Home Assistant custom integration that discovers public open-data sources, interprets bounded samples, and turns user-selected records and measurements into Home Assistant entities.

> [!IMPORTANT]
> Version 0.2.0 is an intentionally shareable preview, not a stable API guarantee. Provider behavior, inferred mappings, temporal plans, and entity models may still change as the validation corpus expands.

## What it supports

The integration currently includes provider and discovery paths for:

- CKAN and CKAN-compatible deployments;
- Socrata;
- ArcGIS Hub and ArcGIS feature services;
- Opendatasoft;
- bounded CSV and JSON resources exposed through supported catalogs;
- bounded GTFS static-feed inspection for validation and future provider work.

Not every portal using one of these technologies is guaranteed to work. Landing pages, redirects, regional discovery endpoints, subpath deployments, localized APIs, authentication requirements, and download-only resources can all affect compatibility. The validation program is therefore organized by shared behavior rather than by city.

## How configuration works

The setup flow uses one source-location field.

- A dataset page, resource URL, API URL, or dataset identifier imports that dataset.
- A portal or catalog root starts bounded catalog discovery.
- A bare identifier may be combined with an optional portal hint.

Reference parsing determines whether the user supplied a portal or a single dataset; there is no separate portal-versus-dataset menu.

During setup and options review, the integration can:

- discover and rank datasets;
- inspect schema and bounded observation samples;
- infer identity, display, timestamp, location, hierarchy, context, and metric roles;
- preserve user-reviewed field assignments during later re-analysis;
- identify wide, long/tidy, event, multi-dimensional, and unknown observation shapes;
- estimate update frequency when usable timestamp history exists;
- expose sampling coverage, time span, truncation, and inferred relationships;
- let users select multiple records, locations, and measurements where supported.

Changing nominal summary fields such as `largest_pollutant` are treated conservatively as context in wide datasets. They are not automatically expanded into large numbers of sparse entities. Long-format metric names are currently exposed as review evidence; automatic materialization remains opt-in future work.

### Temporal inference

Version 0.2 adds an explainable temporal-planning layer for datasets that do not expose one clean timestamp column. It can infer and normalize:

- ISO/RFC-style timestamps and common municipal date/time formats;
- Unix timestamps in seconds or milliseconds;
- separate date and time columns;
- separate year, month, day, hour, minute, and second components;
- partial month/day values using the current date to choose the nearest plausible year.

Naive source timestamps use Home Assistant's configured timezone as the fallback. Explicit source offsets remain authoritative. Implausibly future values and provider-administrative timestamps are penalized during plan scoring.

## Home Assistant entities and history

Configured datasets create stable record-scoped devices and sensors where a useful identity field exists. Datasets without a stable record key retain a dataset-level model.

The integration:

- creates measurement sensors for accepted numeric observations;
- exposes semantic metadata, dimensions, source timestamps, and freshness diagnostics;
- keeps bounded observation history from refreshes;
- imports supported short-term and hourly statistics into Home Assistant Recorder;
- creates a latest-observation timestamp sensor;
- estimates source frequency and reports staleness relative to expected update waves;
- reconciles deselected records and obsolete entities without relying on sparse provider responses.

Historical backfill beyond the bounded refresh window is planned as a separate resumable subsystem and is not performed automatically.

## Installation with HACS

Until this repository is in the default HACS catalog:

1. Open HACS in Home Assistant.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/jmping/ha-open-data` as an **Integration** repository.
4. Install **Open Data**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and select **Open Data**.

For a manual development install, copy `custom_components/open_data` to:

```text
<config>/custom_components/open_data
```

## Home Assistant actions

The integration registers response-capable actions for discovery, inspection, refresh, and support:

- `open_data.inspect_portal`
- `open_data.scan_portal`
- `open_data.search_datasets`
- `open_data.inspect_dataset`
- `open_data.refresh_entry`
- `open_data.feedback_preview`

`inspect_dataset` returns bounded interpretation evidence, including observation shape, proposed field roles, sampling diagnostics, inferred relationships, and guarded long-format previews.

`feedback_preview` creates a metadata-only preview and does not transmit data. Feedback upload remains opt-in and is not enabled until a collector contract exists.

## Known limitations

The 0.2 preview deliberately favors bounded, conservative behavior over trying to infer everything automatically.

- High-cardinality record sets are prevented from auto-materializing observation/sample IDs as Home Assistant entities, but the options UI can still present a large bounded choice list. Searchable and progressively hierarchical selection is still needed for PFAS-scale datasets.
- Temporal plans are inferred at runtime and are explainable in code, but they are not yet persisted as a user-reviewable config artifact.
- Provider coverage is broad but not universal, especially for authenticated APIs, statistical systems, unusual landing pages, and download-only resources.
- Automatic materialization of reviewed long-format metric dimensions remains deferred to avoid sparse entity explosions.
- Large historical backfill is intentionally not automatic and requires a resumable, rate-limited subsystem.

Please file a bug with the portal/dataset URL, Home Assistant version, and the Open Data diagnostic block when an import fails.

## Validation strategy

Validation is organized into shared engineering classes rather than one issue per city:

1. [Portal crawling and canonicalization](https://github.com/jmping/ha-open-data/issues/53)
2. [Cross-city canonical data-label coverage](https://github.com/jmping/ha-open-data/issues/54)
3. [Non-English portal and provider compatibility](https://github.com/jmping/ha-open-data/issues/55)
4. [Evidence-based multilingual data-label mappings](https://github.com/jmping/ha-open-data/issues/56)
5. [Catalog, file, feed, and statistical structure compatibility](https://github.com/jmping/ha-open-data/issues/57)
6. [Bounded validation corpus and coverage matrix](https://github.com/jmping/ha-open-data/issues/58)

City and regional URLs are retained as fixtures in a common matrix. New examples should normally extend an existing platform, language, label, or feed-structure class rather than introduce city-specific runtime code.

See [Validation strategy](docs/VALIDATION_STRATEGY.md) and [Schema corpus](docs/schema-corpus.md).

## Privacy and boundedness

The integration is designed around bounded public-data access:

- catalog, sample, observation, archive, and history operations have explicit limits;
- normal CI uses deterministic offline fixtures rather than third-party availability;
- scheduled or manual live checks publish artifacts without making routine CI depend on public portals;
- corpus samples must not contain credentials, personal information, sensitive records, or complete source datasets;
- user-reviewed mappings remain authoritative over automatic inference.

The integration stores a random local installation identifier for privacy-safe demand deduplication. Feedback payloads exclude dataset records, credentials, account data, IP addresses, and location history.

## Development roadmap

The near-term roadmap focuses on:

- persisting temporal plans and exposing timestamp diagnostics for review;
- replacing large flat record selectors with searchable/hierarchical selection;
- improving observation-model review and bounded candidate selection;
- expanding crawler and provider-family coverage;
- deriving canonical labels from repeated cross-city evidence;
- strengthening multilingual and non-Latin-script compatibility;
- validating generic feed structures without city-specific adapters.

Larger deferred work is tracked separately:

- [Reviewed observation graphs and long-format sensor definitions](https://github.com/jmping/ha-open-data/issues/51)
- [Resumable bounded historical backfill](https://github.com/jmping/ha-open-data/issues/52)

See [Project plan](docs/PLAN.md), [Issue 6 future plan](docs/ISSUE6_FUTURE_PLAN.md), and the [changelog](CHANGELOG.md).

## Validation and contribution rules

Every relevant pull request runs compilation, regression tests, Ruff, repository metadata validation, and Home Assistant lifecycle tests. The compatibility gate is pinned to Home Assistant 2026.9.0 for the 0.2.0 shareable cut. Live third-party checks are isolated from normal CI.

Useful contributions include:

- portal and dataset URLs that exercise a shared discovery pattern;
- bounded metadata and schema fixtures;
- real field labels with language, domain, and provenance;
- feed response envelopes and capability diagnostics;
- regression tests for provider, language, observation-shape, and failure behavior.

Changes should remain bounded, deterministic, reviewable, and reversible. See [Development policy](docs/DEVELOPMENT_POLICY.md).

## License

MIT
