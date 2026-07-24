# Issue #6 follow-on plan

This note records the work intentionally deferred after the bounded observation-analysis slices.

## Near-term interpretation work

- Feed bounded observation evidence into dataset inspection and review.
- Use temporal stability to recommend identity, display, context, metric, and administrative roles while preserving user-reviewed assignments.
- Preview long-format metric streams without automatically creating entities.
- Treat changing nominal summary fields such as `largest_pollutant` as attributes/context unless they are explicitly reviewed as a bounded metric-name dimension. A nominal field in an otherwise wide dataset must not create one mostly-empty entity per observed label.
- Expose descriptive hierarchy and bounded candidate-selection recommendations without changing Home Assistant device ancestry automatically.
- Add conservative newest/oldest provider candidate windows where supported.

## Deferred product work

### Runtime entity materialization

- Automatic long-format sensor creation.
- Parent devices and `via_device` hierarchy.
- Large or unrestricted default entity imports.
- Per-entity provider-query fan-out.

These require explicit review, cardinality limits, stable unique-ID migration, and rollback behavior.

### Historical backfill

- Paginated provider history contracts.
- Backfill restricted to accepted entities and metrics.
- Resumable checkpoints stored outside config-entry data.
- Cancellation, rate limiting, batch limits, recorder protection, and portal backoff.

Backfill should be designed as a separate subsystem rather than extending bounded interpretation queries piecemeal.

## Safety invariants

- User-reviewed role assignments remain authoritative.
- Analyzer output is advisory until explicitly accepted.
- Entity and stream counts are estimated and capped before creation.
- High-cardinality or sparse nominal dimensions are rejected as stream definitions by default.
- Changing nominal summary fields remain attributes/context in wide datasets unless the user explicitly opts into a bounded stream interpretation.
- No analysis or review operation downloads unbounded history.
