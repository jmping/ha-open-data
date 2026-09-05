# Open Data for Home Assistant

A Home Assistant custom integration that discovers public open-data sources, interprets bounded samples, and turns user-selected records and measurements into Home Assistant entities.

> [!IMPORTANT]
> Version 0.2.0 is the first stable public-preview release. Provider coverage and inferred mappings will continue to expand, but the config-entry, temporal, freshness, and entity-selection behavior is now treated as release-stable within the 0.2 line.

## What it supports

The integration currently includes provider and discovery paths for:

- CKAN and CKAN-compatible deployments;
- Socrata;
- ArcGIS Hub and ArcGIS feature services;
- Opendatasoft;
- bounded CSV and JSON resources exposed through supported catalogs;
- bounded GTFS static-feed inspection for validation and future provider work.

Not every portal using one of these technologies is guaranteed to work. Landing pages, redirects, regional discovery endpoints, subpath deployments, localized APIs, authentication requirements, and download-only resources can all affect compatibility. The validation program is organized by shared behavior rather than by city.

## How configuration works

The setup flow uses one source-location field.

- A dataset page, resource URL, API URL, or dataset identifier imports that dataset.
- A portal or catalog root starts bounded catalog discovery.
- A bare identifier may be combined with an optional portal hint.

During setup and options review, the integration can:

- discover and rank datasets;
- inspect schema and bounded observation samples;
- infer identity, display, timestamp, location, hierarchy, context, and metric roles;
- preserve user-reviewed field assignments during later re-analysis;
- identify wide, long/tidy, event, multi-dimensional, and unknown observation shapes;
- estimate update frequency when usable timestamp history exists;
- warn on stale measurements and exclude them by default while leaving them selectable;
- expose sampling coverage, time span, truncation, and inferred relationships;
- let users select multiple records, locations, and measurements where bounded stable identities are available.

Changing nominal summary fields such as `largest_pollutant` are treated conservatively as context in wide datasets. They are not automatically expanded into large numbers of sparse entities.

### Temporal inference and overrides

Version 0.2 includes an explainable temporal-planning layer for datasets that do not expose one clean timestamp column. It can infer and normalize:

- ISO/RFC-style timestamps and common municipal date/time formats;
- Unix timestamps in seconds or milliseconds;
- separate date and time columns;
- separate year, month, day, hour, minute, and second components;
- partial month/day values using the current date to choose the nearest plausible year.

The selected temporal plan is persisted and reused on refresh/restart. Explicit source offsets remain authoritative. Naive local timestamps use the resolved IANA timezone, with Home Assistant's configured timezone as the fallback. The options flow can override the inferred timestamp field and timezone when a source is ambiguous.

If no trustworthy timestamp can be identified, the dataset remains importable with recency marked unknown; freshness-based exclusion is not applied merely because time could not be resolved.

### Freshness and stale measurements

Freshness is evaluated per measurement stream where bounded history exists. The review UI shows latest observation evidence and inferred cadence. Measurements that appear stale relative to their own cadence or sibling streams are excluded by default, but remain visible and can be explicitly selected for historical or intentionally infrequent use.

A selected stale stream does not silently present an old value as current state.

### Large datasets

Record/location discovery is bounded. Small proven-stable record sets can be selected normally. When a provider returns the full record-cardinality cap, Open Data treats the universe as high-cardinality and does not present the truncated list as if it were complete. Historical/sample identifiers are not used as persistent Home Assistant entities.

High-cardinality datasets therefore fall back to dataset-wide behavior unless a bounded stable hierarchy/identity has been configured. Richer searchable/paged hierarchy UX can continue to evolve without exposing misleading partial lists.

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

Until this repository is accepted into the default HACS catalog:

1. Open HACS in Home Assistant.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/jmping/ha-open-data` as an **Integration** repository.
4. Install **Open Data**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and select **Open Data**.

HACS releases are versioned from GitHub tags/releases. After installing a newer release in HACS, restart Home Assistant so the updated Python integration is loaded.

For a manual development install, copy `custom_components/open_data` to:

```text
<config>/custom_components/open_data
```

## Home Assistant actions

The integration registers response-capable actions for discovery, inspection, refresh, and support:

- `open_data.scan_portal`
- `open_data.search_datasets`
- `open_data.inspect_dataset`
- `open_data.refresh_entry`
- `open_data.feedback_preview`
- `open_data.failure_report`

`inspect_dataset` returns bounded interpretation evidence, including observation shape, proposed field roles, sampling diagnostics, inferred relationships, and guarded long-format previews.

`failure_report` creates a sanitized, reviewable GitHub issue URL. It does not upload raw dataset rows or require a GitHub token in Home Assistant; the user reviews and submits the issue in their browser.

## Known limitations

The stable 0.2 line deliberately favors bounded, conservative behavior over trying to infer everything automatically.

- Provider coverage is broad but not universal, especially for authenticated APIs, statistical systems, unusual landing pages, newer ArcGIS catalog variants, and download-only resources.
- Richer search/paging for extremely large hierarchies remains iterative; the stable guarantee is that truncated record universes are not shown as complete.
- Manual temporal override currently targets a single timestamp field plus IANA timezone; richer manual editing of component-based plans can be added later.
- Automatic materialization of reviewed long-format metric dimensions remains conservative to avoid sparse entity explosions.
- Large historical backfill is intentionally not automatic and requires a resumable, rate-limited subsystem.

If an import fails, use the `open_data.failure_report` action or file an issue with the portal/dataset URL, Home Assistant version, and Open Data diagnostic block.

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

The integration stores a random local installation identifier for privacy-safe demand deduplication. Failure-report payloads exclude dataset records, credentials, account data, IP addresses, and location history.

## Development roadmap

After the stable 0.2 release, the near-term roadmap is iterative rather than architectural:

- expand the city/language validation corpus;
- support additional shared portal/backend classes such as newer ArcGIS catalog variants;
- improve cross-city canonical labels and multilingual aliases from corpus evidence;
- add richer search/paging for very large inferred hierarchies;
- improve reviewed long-format sensor materialization;
- add resumable bounded historical backfill.

See [Project plan](docs/PLAN.md), [Issue 6 future plan](docs/ISSUE6_FUTURE_PLAN.md), and the [changelog](CHANGELOG.md).

## Validation and contribution rules

Every relevant pull request runs compilation, regression tests, Ruff, repository metadata validation, and Home Assistant lifecycle tests. The 0.2 compatibility gate covers a rolling year of Home Assistant monthly releases (currently 2025.9 through 2026.9), including full lifecycle checks at the oldest supported release, runtime transition boundaries, the previous release, and current stable. Scheduled/manual jobs exercise representative live portal and GTFS corpora separately from normal CI.

Useful contributions include:

- portal and dataset URLs that exercise a shared discovery pattern;
- bounded metadata and schema fixtures;
- real field labels with language, domain, and provenance;
- feed response envelopes and capability diagnostics;
- regression tests for provider, language, observation-shape, and failure behavior.

Changes should remain bounded, deterministic, reviewable, and reversible. See [Development policy](docs/DEVELOPMENT_POLICY.md).

## License

MIT
