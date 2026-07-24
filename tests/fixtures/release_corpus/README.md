# Release regression corpus

This directory stores small, deterministic reproductions of defects found while testing live public-data sources.

Each JSON case must:

- contain no credentials or private data;
- retain only the minimum schema, rows, or request sequence needed to reproduce the defect;
- identify the provider and source shape;
- name at least one automated regression test;
- declare expected identity and freshness behavior where applicable;
- remain usable without network access.

Live URLs are provenance only. Ordinary CI must not depend on those hosts being reachable.
