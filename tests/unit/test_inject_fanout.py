from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN, add_provenance
from pipefault.inject.fanout import JoinFanout


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


def test_fanout_duplicates_exact_dimension_rows_and_facts() -> None:
    frame = _frame()

    result = JoinFanout().apply(frame, severity=0.5, seed=7)

    assert result.affected_units == 3
    assert result.data.height == 18
    assert result.affected_rows == 6
    assert result.realized_severity == pytest.approx(0.5)
    per_id = result.data.group_by(PROVENANCE_COLUMN).len()
    assert per_id.filter(pl.col("len") == 2).height == 6


def test_fanout_copies_carry_occurrence_one_and_perturbed_values() -> None:
    frame = _frame()

    result = JoinFanout(factor=2.0).apply(frame, severity=0.5, seed=7)

    copies = result.data.filter(pl.col(OCCURRENCE_COLUMN) == 1)
    assert copies.height == 6
    originals = result.data.filter(pl.col(OCCURRENCE_COLUMN) == 0)
    keyed = originals.select(["PULocationID", "pickup_date", "zone_avg_duration_prior"]).rename(
        {"zone_avg_duration_prior": "original"}
    )
    matched = copies.join(keyed, on=["PULocationID", "pickup_date"], how="left")
    assert (matched["zone_avg_duration_prior"] == matched["original"] * 2.0).all()


def test_fanout_keeps_schema_and_column_order() -> None:
    frame = _frame()

    result = JoinFanout().apply(frame, severity=0.25, seed=7)

    assert result.data.columns == frame.columns
    assert result.data.schema == frame.schema


def test_fanout_is_deterministic_and_handles_zero() -> None:
    frame = _frame()

    first = JoinFanout().apply(frame, severity=0.5, seed=7)
    second = JoinFanout().apply(frame, severity=0.5, seed=7)
    zero = JoinFanout().apply(frame, severity=0.0, seed=7)

    assert first.data.equals(second.data)
    assert zero.data.equals(frame)
    assert zero.affected_rows == 0


def test_fanout_rejects_missing_columns_and_identity_perturbation() -> None:
    with pytest.raises(ValueError, match="missing D1 columns"):
        JoinFanout().apply(_frame().drop("pickup_date"), severity=0.1, seed=7)
    with pytest.raises(ValueError, match="factor"):
        JoinFanout(factor=1.0).apply(_frame(), severity=0.1, seed=7)
