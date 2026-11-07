"""Deterministic event-time replay for the streaming path.

The replay assigns three things per event: ingestion time, lateness, and
whether the event is still inside the allowed lateness. It does not drop
anything; the watermark step does that explicitly.

Delay groups are chosen by hash rank, so each group has an exact size and
reruns are identical without depending on input order.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipefault.data.provenance import PROVENANCE_COLUMN

INGEST_TIME = "pf_ingest_time"
LATENESS_SECONDS = "pf_lateness_seconds"
WITHIN_LATENESS = "pf_within_lateness"
_ROW = "_pf_replay_row"
_RANK = "_pf_replay_rank"
_DELAY_HASH = "_pf_delay_hash"


@dataclass(frozen=True)
class ReplaySpec:
    """Delay mix for one replay. Shares must sum to at most one."""

    time_column: str = "pf_event_time"
    allowed_lateness_seconds: int = 3600
    on_time_share: float = 0.80
    late_share: float = 0.15
    seed: int = 42

    def __post_init__(self) -> None:
        if self.allowed_lateness_seconds <= 0:
            raise ValueError("allowed_lateness_seconds must be positive")
        for name in ("on_time_share", "late_share"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.on_time_share + self.late_share > 1.0:
            raise ValueError("on_time_share + late_share must be at most 1")


def replay(frame: pl.DataFrame, spec: ReplaySpec) -> pl.DataFrame:
    """Add ingest time, lateness, and within-lateness columns.

    Events with zero delay are on time, events with a delay up to
    ``allowed_lateness_seconds`` are late but inside the watermark, and the
    rest are too late for the watermark.
    """
    if spec.time_column not in frame.columns:
        raise ValueError(f"missing event time column {spec.time_column!r}")
    if frame.height == 0:
        raise ValueError("cannot replay an empty frame")

    height = frame.height
    late_count = round(spec.late_share * height)
    on_time_count = round(spec.on_time_share * height)
    if on_time_count + late_count > height:
        raise ValueError("delay shares select more rows than the frame holds")

    key = PROVENANCE_COLUMN if PROVENANCE_COLUMN in frame.columns else _ROW
    ranked = (
        frame.with_row_index(_ROW)
        .with_columns(
            pl.struct(
                [
                    pl.col(key).alias("key"),
                    pl.lit(spec.seed).alias("seed"),
                ]
            )
            .hash(seed=spec.seed)
            .alias(_RANK),
            pl.struct(
                [
                    pl.col(key).alias("key"),
                    pl.lit(spec.seed).alias("seed"),
                    pl.lit(spec.time_column).alias("time_column"),
                ]
            )
            .hash(seed=spec.seed)
            .alias(_DELAY_HASH),
        )
        .sort(_RANK)
        .with_columns(pl.int_range(0, height, dtype=pl.Int64).alias("_pf_slot"))
    )

    allowed = spec.allowed_lateness_seconds
    delay = (
        (
            pl.when(pl.col("_pf_slot") < on_time_count)
            .then(pl.lit(0, dtype=pl.Int64))
            .when(pl.col("_pf_slot") < on_time_count + late_count)
            .then(1 + pl.col(_DELAY_HASH) % allowed)
            .otherwise(allowed + 1 + pl.col(_DELAY_HASH) % allowed)
        )
        .cast(pl.Int64)
        .alias(LATENESS_SECONDS)
    )

    return (
        ranked.with_columns(delay)
        .with_columns(
            (pl.col(spec.time_column) + pl.duration(seconds=pl.col(LATENESS_SECONDS))).alias(
                INGEST_TIME
            ),
            (pl.col(LATENESS_SECONDS) <= allowed).alias(WITHIN_LATENESS),
        )
        .sort(_ROW)
        .drop([_ROW, _RANK, _DELAY_HASH, "_pf_slot"])
    )


def apply_watermark(
    frame: pl.DataFrame, *, allowed_lateness_seconds: int
) -> tuple[pl.DataFrame, int]:
    """Drop events later than the watermark. Returns the kept frame and count."""
    if LATENESS_SECONDS not in frame.columns:
        raise ValueError(f"missing {LATENESS_SECONDS}; call replay first")
    if allowed_lateness_seconds <= 0:
        raise ValueError("allowed_lateness_seconds must be positive")

    kept = frame.filter(pl.col(LATENESS_SECONDS) <= allowed_lateness_seconds)
    return kept, frame.height - kept.height
