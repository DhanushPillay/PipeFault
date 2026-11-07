from __future__ import annotations

import polars as pl
import pytest

from pipefault.data.provenance import PROVENANCE_COLUMN, add_provenance
from pipefault.inject.coercion import SilentCoercion


def _frame(rows: int = 100) -> pl.DataFrame:
    frame = pl.DataFrame(
        {
            "zone_avg_duration_prior": [60.0 + i for i in range(rows)],
            "passenger_count": [1 + (i % 3) for i in range(rows)],
        }
    )
    return add_provenance(frame, dataset="tlc", file="a.parquet")


def test_coercion_changes_exact_count_and_keeps_schema() -> None:
    frame = _frame()

    result = SilentCoercion().apply(frame, severity=0.20, seed=7)

    changed = (result.data["zone_avg_duration_prior"] != frame["zone_avg_duration_prior"]).sum()
    assert changed == 20
    assert result.affected_rows == 20
    assert result.affected_units == 20
    assert result.realized_severity == pytest.approx(0.20)
    assert result.data.schema == frame.schema
    assert result.data[PROVENANCE_COLUMN].to_list() == frame[PROVENANCE_COLUMN].to_list()


def test_coercion_applies_the_unit_factor() -> None:
    frame = _frame(10)

    result = SilentCoercion(column="zone_avg_duration_prior", factor=1 / 60).apply(
        frame, severity=0.5, seed=7
    )

    changed = result.data.filter(
        pl.col("zone_avg_duration_prior") != frame["zone_avg_duration_prior"]
    )
    originals = frame.filter(pl.col(PROVENANCE_COLUMN).is_in(changed[PROVENANCE_COLUMN].to_list()))
    assert (
        changed["zone_avg_duration_prior"].to_list()
        == (originals["zone_avg_duration_prior"] / 60).to_list()
    )


def test_coercion_truncates_an_integer_column_without_changing_dtype() -> None:
    frame = _frame(10)

    result = SilentCoercion(column="passenger_count", factor=0.5).apply(frame, severity=1.0, seed=7)

    assert result.data.schema["passenger_count"] == frame.schema["passenger_count"]
    expected = [int((1 + (i % 3)) * 0.5) for i in range(10)]
    assert result.data["passenger_count"].to_list() == expected


def test_coercion_is_deterministic_and_handles_zero() -> None:
    frame = _frame()

    first = SilentCoercion().apply(frame, severity=0.2, seed=7)
    second = SilentCoercion().apply(frame, severity=0.2, seed=7)
    zero = SilentCoercion().apply(frame, severity=0.0, seed=7)

    assert first.data.equals(second.data)
    assert zero.data.equals(frame)
    assert zero.affected_rows == 0


def test_coercion_rejects_a_missing_column() -> None:
    with pytest.raises(ValueError, match="missing coercion column"):
        SilentCoercion(column="nope").apply(_frame(5), severity=0.1, seed=7)
