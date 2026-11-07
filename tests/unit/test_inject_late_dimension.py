from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from pipefault.data.provenance import PROVENANCE_COLUMN, add_provenance
from pipefault.inject.late_dimension import LatestVersionJoin


def _frame() -> pl.DataFrame:
    rows = [
        {
            "PULocationID": zone,
            "pickup_date": date(2024, 1, day),
            "zone_avg_duration_prior": float(zone * 10 + day),
            "zone_trip_count_prior": float(zone * 100 + day),
        }
        for zone in (1, 2)
        for day in (1, 2, 3)
        for _ in range(2)
    ]
    return add_provenance(pl.DataFrame(rows), dataset="tlc", file="a.parquet")


def test_latest_join_changes_exact_count_to_latest_values() -> None:
    frame = _frame()

    result = LatestVersionJoin().apply(frame, severity=0.25, seed=7)

    changed = result.data.filter(
        pl.col("zone_avg_duration_prior") != frame["zone_avg_duration_prior"]
    )
    assert changed.height == 3
    assert result.affected_units == 3
    assert result.affected_rows == 3
    assert result.realized_severity == pytest.approx(0.25)
    assert result.data.columns == frame.columns
    for row in changed.iter_rows(named=True):
        assert row["zone_avg_duration_prior"] == float(row["PULocationID"] * 10 + 3)
        assert row["zone_trip_count_prior"] == float(row["PULocationID"] * 100 + 3)


def test_latest_join_skips_facts_already_on_the_newest_version() -> None:
    frame = _frame()

    result = LatestVersionJoin().apply(frame, severity=1.0, seed=7)

    newest = frame.filter(pl.col("pickup_date") == date(2024, 1, 3))
    assert result.affected_units == frame.height - newest.height == 8
    assert result.realized_severity == pytest.approx(8 / frame.height)
    untouched = result.data.filter(pl.col("pickup_date") == date(2024, 1, 3))
    assert (
        untouched["zone_avg_duration_prior"].to_list()
        == newest["zone_avg_duration_prior"].to_list()
    )


def test_latest_join_is_deterministic_and_handles_zero() -> None:
    frame = _frame()

    first = LatestVersionJoin().apply(frame, severity=0.5, seed=7)
    second = LatestVersionJoin().apply(frame, severity=0.5, seed=7)
    zero = LatestVersionJoin().apply(frame, severity=0.0, seed=7)

    assert first.data.equals(second.data)
    assert zero.data.equals(frame)
    assert zero.affected_rows == 0


def test_latest_join_rejects_missing_columns() -> None:
    frame = _frame().drop("zone_trip_count_prior")

    with pytest.raises(ValueError, match="missing D3 columns"):
        LatestVersionJoin().apply(frame, severity=0.1, seed=7)


def test_affected_ids_are_real_provenance_ids() -> None:
    frame = _frame()

    result = LatestVersionJoin().apply(frame, severity=0.5, seed=7)

    changed_ids = set(
        result.data.filter(pl.col("zone_avg_duration_prior") != frame["zone_avg_duration_prior"])[
            PROVENANCE_COLUMN
        ]
    )
    assert changed_ids <= set(frame[PROVENANCE_COLUMN])
    assert len(changed_ids) == 6
