"""D3: as-of join bug. Every fact joins the newest dimension version."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipefault.data.provenance import PROVENANCE_COLUMN
from pipefault.features.asof import build_versions, latest_lookup
from pipefault.inject.base import InjectionResult, select_top, validate_severity

_LATEST_SUFFIX = "_pf_latest"


@dataclass(frozen=True)
class LatestVersionJoin:
    """Use the latest version of the dimension instead of the event-time one."""

    name: str = "D3"
    key: str = "PULocationID"
    date_column: str = "pickup_date"
    value_columns: tuple[str, ...] = (
        "zone_avg_duration_prior",
        "zone_trip_count_prior",
    )

    def apply(self, frame: pl.DataFrame, *, severity: float, seed: int) -> InjectionResult:
        validate_severity(severity)
        required = [self.key, self.date_column, *self.value_columns, PROVENANCE_COLUMN]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"missing D3 columns: {', '.join(missing)}")

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

        versions = build_versions(
            frame,
            key=self.key,
            date_column=self.date_column,
            value_columns=self.value_columns,
        )
        latest = latest_lookup(
            versions,
            key=self.key,
            version_date=self.date_column,
            value_columns=self.value_columns,
        )

        # A fact already on its key's newest date cannot change; target only
        # facts that have an older version available.
        latest_dates = latest.select([self.key, pl.col(self.date_column).alias("_pf_latest_date")])
        eligible = (
            frame.select([PROVENANCE_COLUMN, self.key, self.date_column])
            .join(latest_dates, on=self.key, how="left")
            .filter(pl.col(self.date_column) < pl.col("_pf_latest_date"))
        )
        target_count = min(count, eligible.height)
        chosen_ids = select_top(eligible, count=target_count, seed=seed)[
            PROVENANCE_COLUMN
        ].to_list()

        data = frame.join(
            latest.select([self.key, *self.value_columns]),
            on=self.key,
            how="left",
            suffix=_LATEST_SUFFIX,
        )
        hit = pl.col(PROVENANCE_COLUMN).is_in(chosen_ids)
        for column in self.value_columns:
            data = data.with_columns(
                pl.when(hit)
                .then(pl.col(f"{column}{_LATEST_SUFFIX}"))
                .otherwise(pl.col(column))
                .alias(column)
            )
        data = data.drop([f"{column}{_LATEST_SUFFIX}" for column in self.value_columns])

        changed = int(
            data.select(
                pl.any_horizontal(
                    [pl.col(column) != frame[column] for column in self.value_columns]
                ).sum()
            ).item()
        )
        return InjectionResult(
            name=self.name,
            severity=severity,
            realized_severity=changed / frame.height,
            affected_units=target_count,
            affected_rows=changed,
            data=data,
            details={
                "key": self.key,
                "value_columns": list(self.value_columns),
                "targeted_rows": target_count,
                "changed_rows": changed,
                "version_keys": latest.height,
            },
        )
