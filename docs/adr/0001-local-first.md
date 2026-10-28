# ADR 0001: Local-first build with Make and a Python CLI

- Status: accepted
- Date: 2026-10-28

## Context

The project must be reproducible for a paper artifact, runnable by a student on
one machine, and credible to data-engineering reviewers. Managed cloud services
and a full orchestrator add cost and failure modes without improving the
measurement study.

## Decision

- Run the demo with Docker Compose on one machine.
- Orchestrate with a `Makefile` plus a Typer CLI, not Airflow, Prefect, or Dagster.
- Use Spark Structured Streaming in local mode only for event-time validation.
- Use real public datasets; defects are injected into real records, never
  generated rows.

## Consequences

- A clean clone can reproduce the core results without cloud credentials.
- The artifact demonstrates pipeline engineering, testing, and packaging, but
  not cluster operations or managed-service administration.
- A cloud deployment remains optional and is not part of the paper's claims.
