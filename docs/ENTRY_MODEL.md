# Open Data entry and polling model

The integration separates catalog ownership from data-stream ownership.

## Portal entries

A portal entry represents one institution-level CKAN or Socrata catalog. It owns provider detection, catalog discovery, and ranking. It does not poll dataset rows or create sensor entities.

Configuring a portal launches a new dataset flow. The selected dataset is created as a separate config entry.

## Dataset entries

A dataset entry is independently updating. It may originate from portal discovery or a manual URL, API endpoint, or identifier. Each dataset entry owns its coordinator, selected fields, selected stream location, availability, reload lifecycle, and profile cache.

## Accepted direct references

The parser recognizes common CKAN and Socrata portal roots, dataset pages, resource pages, Action API URLs, SODA resource/view endpoints, human dataset pages ending in a four-by-four ID, and bare identifiers accompanied by a portal URL.

## Location-aware streams

Recent rows are inspected for likely station, site, location, or sensor fields. Summary and aggregate rows rank before physical locations. Other locations are ranked using Euclidean latitude/longitude distance from Home Assistant's configured location. This distance is only a local relative ranking, not a physical distance measurement.

## Adaptive large-dataset profiling

Each dataset entry maintains a persistent intelligence profile in Home Assistant storage. Profiling is delayed after setup and then repeated every six hours, so initial configuration remains responsive.

The profiler obtains the provider's row count and samples small pages from the beginning, middle, and end. It records page hashes, timestamp ordering, row-count growth, changing regions, observation count, last profile time, inferred newest region, and confidence.

Timestamp ordering provides a deterministic result when available:

- ascending timestamps imply newest rows are at the end;
- descending timestamps imply newest rows are at the beginning;
- inconsistent timestamp samples mark the dataset unstable.

Without a timestamp field, repeated page-hash observations build confidence about whether the beginning, middle, or end changes. Middle rewrites or multiple changing regions reduce confidence and mark the dataset unstable.

## Bounded adaptive pagination

CKAN and Socrata providers expose offset pagination and inexpensive row counts. Dataset polling uses the learned profile:

- timestamped datasets are explicitly sorted newest-first;
- end-appending datasets begin at the final page and walk backward;
- beginning-changing or unknown datasets start at the first page and walk forward;
- location filtering continues page by page until a matching row is found;
- scans are bounded to avoid unbounded downloads or blocking Home Assistant.

Current safety limits are 500 rows per page and 40 pages per refresh. These bounds allow a selected location to be found across substantially larger datasets without downloading the complete table.

## Identity and migration

Portal unique IDs use `portal:<provider>:<portal URL>`. Dataset unique IDs use `dataset:<provider>:<portal URL>:<dataset ID>:<resource ID>`. Version 1 entries migrate to version 2 as dataset entries.

## Extension boundary

Reference parsing, provider APIs, dataset profiling, and config-entry ownership are separate layers. ArcGIS, OpenDataSoft, CSV, JSON, or arbitrary REST providers can implement the pagination contract without changing the portal/dataset entry model or intelligence layer.
