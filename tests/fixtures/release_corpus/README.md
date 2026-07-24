# Release validation corpus

This directory stores small, reviewable reproductions of defects found while testing live public-data sources.

Each JSON case must contain:

- source/provider metadata and the date of the live observation;
- a concise failure description;
- a bounded, redacted schema and sample;
- expected identity, role, stream, freshness, or recovery behavior;
- a pytest node ID that protects the behavior.

Guardrails enforced by `tests/test_release_corpus.py`:

- at most 12 sample rows and 64 fields;
- no credential-like keys or declared personal data;
- a maximum serialized case size of 32 KiB;
- unique case IDs;
- every referenced regression-test file must exist.

When a live test exposes a bug, add or update one case before changing runtime behavior. The retained sample should be the minimum evidence needed to reproduce the failure, not a copy of the source dataset.
