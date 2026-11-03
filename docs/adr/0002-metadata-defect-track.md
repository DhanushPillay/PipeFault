# ADR 0002: Metadata-borne defect track (post-pilot)

## Status

Proposed (post-pilot).

## Decision

Add a separate defect track for defects visible only through freshness, lineage, or provenance metadata (SARC-DQ style), not through payload values. Analyzed separately; does not enter the H1 silent-vs-volume contrast.

## Rationale

Payload-only injection misses the most dangerous class of defects (stale/superseded records). Adding this track strengthens construct validity after the eight-defect pilot is interpretable.

## Consequences

- New injector module `pipefault/inject/metadata.py`.
- Separate result table (R6) and threat-to-validity note.
- No change to pre-registered H1-H4.
- Deferred until week 3 pilot passes.
