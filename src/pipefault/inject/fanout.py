"""D1: join fanout. A duplicated dimension row multiplies its facts."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipefault.data.provenance import PROVENANCE_COLUMN, add_occurrence
from pipefault.inject.base import InjectionResult, select_top, validate_severity

_COPY = "_pf_fanout_copy"


@dataclass(frozen=True)
class JoinFanout:
    """Duplicate a fraction of dimension rows, then join facts to the result.

    The dimension is keyed the same way as the zone statistics join in the TLC
    pipeline: one row per zone and pickup date. Each duplicated row carries a
    perturbed value, so a later ``DISTINCT`` cannot silently collapse it.
    """

    name: str = "D1"
    key_columns: tuple[str, ...] = ("PULocationID", "pickup_date")
    value_columns: tuple[str, ...] = (
        "zone_avg_duration_prior",
        "zone_trip_count_prior",
    )
    factor: float = 1.1

    def apply(self, frame: pl.DataFrame, *, severity: float, seed: int) -> InjectionResult:
        validate_severity(severity)
        required = [*self.key_columns, *self.value_columns, PROVENANCE_COLUMN]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"missing D1 columns: {', '.join(missing)}")
        if self.factor == 1.0:
            raise ValueError("factor must differ from 1.0")

        dimension = (
            frame.select([*self.key_columns, *self.value_columns])
            .unique(subset=list(self.key_columns), keep="first", maintain_order=True)
            .with_columns(pl.lit(0, dtype=pl.UInt8).alias(_COPY))
        )
        count = round(severity * dimension.height)
        if count == 0:
            return InjectionResult(
                name=self.name,
                severity=severity,
                realized_severity=0.0,
                affected_units=0,
                affected_rows=0,
                data=frame,
            )

        chosen = select_top(dimension, count=count, seed=seed, keys=self.key_columns).with_columns(
            pl.lit(1, dtype=pl.UInt8).alias(_COPY),
            *[(pl.col(column) * self.factor).alias(column) for column in self.value_columns],
        )
        enlarged = pl.concat([dimension, chosen], how="vertical_relaxed")
        data = (
            frame.drop(self.value_columns)
            .join(enlarged, on=list(self.key_columns), how="left")
            .sort([PROVENANCE_COLUMN, _COPY])
        )
        data = add_occurrence(data).drop(_COPY).select(frame.columns)

        added = data.height - frame.height
        return InjectionResult(
            name=self.name,
            severity=severity,
            realized_severity=count / dimension.height,
            affected_units=count,
            affected_rows=added,
            data=data,
            details={
                "key_columns": list(self.key_columns),
                "duplicated_dimension_rows": count,
                "dimension_rows": dimension.height,
                "added_rows": added,
                "row_inflation": min(1.0, added / frame.height),
                "factor": self.factor,
            },
        )
