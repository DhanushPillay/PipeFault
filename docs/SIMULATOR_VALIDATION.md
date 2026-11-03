# Simulator validation

## 1. Goal

Validate the custom event-time simulator against Spark Structured Streaming on a small seeded stream. Gate: at least 99% row-level agreement.

## 2. Semantics to match

- Watermark = max event time seen in the batch minus the delay threshold, computed at the start of the next trigger.
- An event is dropped when its event time is below the watermark; events at or above it are retained.
- Windows assigned by flooring event time to the window grid (origin 1970-01-01 UTC).
- Sliding windows assign one event to multiple overlapping windows.
- Boundary inclusivity: `event_time < watermark` drops.
- Per-batch (not per-row) max event time.
- Handle out-of-range event times (TLC spans 2002-2026); a single future timestamp can inflate the watermark.

## 3. Methodology

- Seeded synthetic stream with controlled event-time skew, lateness, duplicates, empty batches.
- Run identical inputs through both engines with the same watermark threshold and window parameters.
- Compare multisets of emitted rows (window start/end, group key, aggregates, dropped/late counts), not row order.
- Edge cases: all-late batches, events exactly on the watermark, sliding overlaps, null/invalid timestamps.
- Record Spark version, config, and a reproducible validation report in CI.

## 4. Pitfalls to avoid

- Using processing time instead of event time for the watermark.
- Advancing the watermark per row or per arrival instead of per batch max.
- Off-by-one boundary drops.
- Mishandling out-of-order rows within a batch.
- Timezone/origin mismatches in window flooring.
- Forgetting sliding-window multiplicity.
- Coupling validation to Spark's file-listing order.

## 5. Downgrade rule

If row-level agreement is below 99%, or watermark/window semantics cannot be reproduced, or validation slips past the week 8 gate: drop the streaming claim and report the harness as a deterministic micro-batch event-time simulator. Retain watermark/lateness as simulated semantics and document the construct-validity threat. Even aggregate-only (not row-level) agreement triggers a downgrade.

## 6. Real-data check

Repeat the agreement measurement on TLC subsets with real timestamp skew, not only synthetic streams. Report confidence intervals on agreement.
