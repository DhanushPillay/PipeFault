"""D5: duplicate ingestion. Replay a fraction of events with new ingest times."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipefault.data.provenance import (
    PROVENANCE_COLUMN,
    add_occurrence,
)
from pipefault.inject.base import InjectionResult, select_top, validate_severity
from pipefault.simulate.replay import INGEST_TIME


@dataclass(frozen=True)
class DuplicateIngestion:
    """At-least-once delivery replays exact copies of source events."""

    name: str = "D5"
    max_delay_seconds: int = 300

    def apply(self, frame: pl.DataFrame, *, severity: float, seed: int) -> InjectionResult:
        validate_severity(severity)
        if INGEST_TIME not in frame.columns:
            raise ValueError(f"D5 requires {INGEST_TIME}; run replay first")

        count = round(severity * frame.height)
        if count == 0:
            return InjectionResult(
                name=self.name,
                severity=severity,
                realized_severity=0.0,
                affected_units=0,
                affected_rows=0,
                data=frame,
            )

        chosen = select_top(frame, count=count, seed=seed)
        delay = (
            pl.struct([pl.col(PROVENANCE_COLUMN).alias("row")]).hash(seed=seed)
            % self.max_delay_seconds
            + 1
        ).cast(pl.Int64)
        copies = chosen.with_columns(
            (pl.col(INGEST_TIME) + pl.duration(seconds=delay)).alias(INGEST_TIME)
        )
        data = add_occurrence(pl.concat([frame, copies], how="vertical_relaxed"))

        return InjectionResult(
            name=self.name,
            severity=severity,
            realized_severity=count / frame.height,
            affected_units=count,
            affected_rows=count,
            data=data,
            details={
                "duplicated_rows": count,
                "rows_before": frame.height,
                "rows_after": data.height,
            },
        )
