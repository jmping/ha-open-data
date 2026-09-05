# Source seed registries

The source-discovery corpus is intentionally **source-centric**, not a global dataset index.

External registries such as data.gov portal lists, Open Data Inception, Data Portals, CKAN ecosystem registries, and curated regional audits are useful as **candidate source seeds**. Their entries are discovery leads, not assertions that a portal is current, supported, or relevant to every user in the named region.

## Seed record

A seed should retain only bounded provenance and discovery metadata:

- `name`
- `url`
- `provenance`
- `source_type` (city, county, state/province, national, agency/network, etc.)
- `region_hint`
- `language_hint`

CSV inputs are also supported. The sampler recognizes common columns such as `name`, `url`, `type`, `region`, `location`, `country`, and `language`.

## Daily sampling

`scripts/sample_source_registry.py`:

1. loads and canonicalizes seed URLs;
2. deduplicates sources by canonical URL;
3. rotates through sources without replacement within each cycle;
4. samples 50 sources per day by default;
5. performs bounded portal/provider inspection;
6. samples at most 20 catalog entries;
7. runs bounded searches for Home Assistant-relevant topic intents;
8. writes a diagnostic artifact.

Dataset IDs/titles in a report are **run evidence only**. They are not automatically copied into a persistent global registry.

At 2,600 sources and 50 sources/day, a complete source pass is roughly 52 days before rotation repeats.

## Promotion into the curated source corpus

A seed can be promoted into a richer source/search profile after evidence shows that it is worth retaining. Useful evidence includes:

- the endpoint still resolves to a canonical live source;
- provider/feed family is recognized;
- geographic/formal coverage can be described;
- practical region of relevance can be stated conservatively;
- catalog/search capabilities are known;
- source/language-specific search terms produce useful bounded candidates;
- broad dataset families are observed repeatedly;
- compatibility quirks and failure modes are understood.

Promotion should retain **search strategy and source metadata**, not exhaustive dataset IDs.

## Search intents

The initial generic topic probes are:

- weather
- air quality
- traffic
- transit
- water
- flood
- wildfire
- earthquake
- volcano
- outage

These are deliberately broad English intents. As multilingual audits accumulate evidence, source profiles may add localized terms or provider-native filters. Avoid building a speculative giant multilingual dictionary; learn search terms from successful portal audits.

## Relationship to location-first discovery

The eventual discovery flow should be:

`Home Assistant location → relevant source profiles → bounded topic searches → inspect/rank candidate datasets → user chooses import`

The seed registry is therefore a way to discover and test **where to search**. It is not intended to answer **which exact dataset** should always be installed.
