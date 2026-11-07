"""D6: silent coercion. Shift units for a fraction of values without a schema change."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN
from pipefault.inject.base import InjectionResult, select_top, validate_severity

_HIT = "_pf_coercion_hit"


@dataclass(frozen=True)
class SilentCoercion:
    """A unit or truncation bug that leaves the column name and dtype intact."""

    name: str = "D6"
    column: str = "zone_avg_duration_prior"
    factor: float = 1 / 60

    def apply(self, frame: pl.DataFrame, *, severity: float, seed: int) -> InjectionResult:
        validate_severity(severity)
        if self.column not in frame.columns:
            raise ValueError(f"missing coercion column {self.column!r}")
        if self.factor == 0:
            raise ValueError("factor must be non-zero")

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

        dtype = frame.schema[self.column]
        chosen = (
            select_top(frame, count=count, seed=seed)
            .select([PROVENANCE_COLUMN, OCCURRENCE_COLUMN])
            .with_columns(pl.lit(True).alias(_HIT))
        )
        data = (
            frame.join(chosen, on=[PROVENANCE_COLUMN, OCCURRENCE_COLUMN], how="left")
            .with_columns(
                pl.when(pl.col(_HIT).is_not_null())
                .then((pl.col(self.column) * self.factor).cast(dtype))
                .otherwise(pl.col(self.column))
                .alias(self.column)
            )
            .drop(_HIT)
        )

        changed = int((data[self.column] != frame[self.column]).sum())
        return InjectionResult(
            name=self.name,
            severity=severity,
            realized_severity=changed / frame.height,
            affected_units=count,
            affected_rows=changed,
            data=data,
            details={
                "column": self.column,
                "factor": self.factor,
                "selected_rows": count,
                "changed_values": changed,
            },
        )
