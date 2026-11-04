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

## 5. Scientific-first amendment

The project prioritizes valid measurements over additional technologies. The
first complete result must be runnable with the local Python, Polars or DuckDB,
CPU LightGBM, deterministic configs, and the existing test suite. Spark may be
used to validate a small event-time subset, but it is not part of the primary
execution path.

The RTX 4060 is optional and 16 GB of RAM is the baseline target. Monthly
partitioning, compact feature caches, and one or two workers are preferred over
distributed execution. FastAPI, Streamlit, Redpanda, MLPs, and the full grid
are deferred until the TLC pilot has produced interpretable scientific results.

This amendment is satisfied only when the project can report a clean baseline,
eight tested defect mechanisms, paired controls, repeated seeds, confidence
intervals, alarm-quality metrics, and a fitted corruption-space law with one
transfer test. A larger stack without those results is not progress toward the
paper.
