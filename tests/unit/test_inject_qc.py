from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

import polars as pl
import pytest

from pipefault.data.provenance import PROVENANCE_COLUMN, add_provenance
from pipefault.inject.coercion import SilentCoercion
from pipefault.inject.duplicate import DuplicateIngestion
from pipefault.inject.fanout import JoinFanout
from pipefault.inject.late_dimension import LatestVersionJoin
from pipefault.inject.qc import verify_injection
from pipefault.simulate.replay import ReplaySpec, replay


def _stats_frame() -> pl.DataFrame:
    records = [
        {
            "PULocationID": zone,
            "pickup_date": date(2024, 1, day),
            "zone_avg_duration_prior": float(zone * 10 + day),
            "zone_trip_count_prior": float(zone * 100 + day),
            "passenger_count": 1 + (index % 3),
        }
        for index, (zone, day) in enumerate(
            (zone, day) for zone in (1, 2) for day in (1, 2, 3) for _ in range(2)
        )
    ]
    return add_provenance(pl.DataFrame(records), dataset="tlc", file="a.parquet")


def _replayed(rows: int = 12) -> pl.DataFrame:
    start = datetime(2024, 1, 1)
    frame = add_provenance(
        pl.DataFrame({"tpep_pickup_datetime": [start + timedelta(minutes=i) for i in range(rows)]}),
        dataset="tlc",
        file="a.parquet",
    )
    return replay(frame, ReplaySpec(time_column="tpep_pickup_datetime", seed=42))


def test_qc_accepts_every_pilot_injector() -> None:
    stats = _stats_frame()
    verify_injection(stats, JoinFanout().apply(stats, severity=0.5, seed=7))
    verify_injection(stats, LatestVersionJoin().apply(stats, severity=0.5, seed=7))
    verify_injection(
        stats,
        SilentCoercion(column="passenger_count", factor=0.5).apply(stats, severity=0.5, seed=7),
    )

    replayed = _replayed()
    verify_injection(replayed, DuplicateIngestion().apply(replayed, severity=0.25, seed=7))


def test_qc_rejects_a_lying_count() -> None:
    frame = _stats_frame()
    result = JoinFanout().apply(frame, severity=0.5, seed=7)

    with pytest.raises(RuntimeError, match="row count mismatch"):
        verify_injection(frame, replace(result, affected_rows=result.affected_rows + 1))


def test_qc_rejects_a_column_or_schema_change() -> None:
    frame = _stats_frame()
    result = SilentCoercion(column="passenger_count", factor=0.5).apply(frame, severity=0.5, seed=7)

    extra = result.data.with_columns(pl.lit(1).alias("extra"))
    with pytest.raises(RuntimeError, match="column set changed"):
        verify_injection(frame, replace(result, data=extra))


def test_qc_rejects_dropped_rows() -> None:
    frame = _stats_frame()
    result = SilentCoercion(column="passenger_count", factor=0.5).apply(frame, severity=0.5, seed=7)
    dropped = result.data.filter(pl.col(PROVENANCE_COLUMN) != result.data[PROVENANCE_COLUMN][0])

    with pytest.raises(RuntimeError, match="dropped"):
        verify_injection(frame, replace(result, data=dropped))


def test_qc_rejects_a_lost_duplicate_row() -> None:
    frame = _replayed()
    result = DuplicateIngestion().apply(frame, severity=0.25, seed=7)
    shortened = result.data.head(result.data.height - 1)

    with pytest.raises(RuntimeError, match="realized severity"):
        verify_injection(frame, replace(result, data=shortened))


def test_qc_rejects_an_unrelated_column_change() -> None:
    stats = _stats_frame()
    coercion = SilentCoercion(column="passenger_count", factor=0.5).apply(
        stats, severity=0.5, seed=7
    )
    tampered = coercion.data.with_columns(
        (pl.col("zone_avg_duration_prior") + 1).alias("zone_avg_duration_prior")
    )

    with pytest.raises(RuntimeError, match="unrelated column"):
        verify_injection(stats, replace(coercion, data=tampered))

    asof = LatestVersionJoin().apply(stats, severity=0.5, seed=7)
    shifted = asof.data.with_columns((pl.col("PULocationID") + 10).alias("PULocationID"))
    with pytest.raises(RuntimeError, match="unrelated column"):
        verify_injection(stats, replace(asof, data=shifted))
