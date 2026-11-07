from __future__ import annotations

import polars as pl
import pytest

from pipefault.data.provenance import add_provenance
from pipefault.inject.base import (
    InjectionResult,
    derive_seed,
    select_top,
    validate_severity,
)
from pipefault.inject.registry import available, get, register


def _frame(rows: int = 100) -> pl.DataFrame:
    frame = pl.DataFrame({"value": list(range(rows))})
    return add_provenance(frame, dataset="tlc", file="a.parquet")


def test_derive_seed_is_isolated_per_condition() -> None:
    base = derive_seed(42, defect="D5", severity=0.1, purpose="rows")
    again = derive_seed(42, defect="D5", severity=0.1, purpose="rows")
    other_defect = derive_seed(42, defect="D6", severity=0.1, purpose="rows")
    other_severity = derive_seed(42, defect="D5", severity=0.2, purpose="rows")
    other_purpose = derive_seed(42, defect="D5", severity=0.1, purpose="keys")

    assert base == again
    assert len({base, other_defect, other_severity, other_purpose}) == 4


def test_select_top_takes_an_exact_deterministic_subset() -> None:
    frame = _frame()

    subset = select_top(frame, count=10, seed=7)
    again = select_top(frame, count=10, seed=7)
    other = select_top(frame, count=10, seed=8)

    assert subset.height == 10
    assert subset["pf_row_id"].to_list() == again["pf_row_id"].to_list()
    assert subset["pf_row_id"].to_list() != other["pf_row_id"].to_list()


def test_select_top_edges_and_key_columns() -> None:
    frame = _frame()
    keys = frame.select("value").unique()

    empty = select_top(frame, count=0, seed=7)
    everything = select_top(frame, count=frame.height, seed=7)
    by_value = select_top(keys, count=3, seed=7, keys=["value"])

    assert empty.height == 0
    assert empty.columns == frame.columns
    assert everything.equals(frame)
    assert by_value.height == 3


def test_select_top_rejects_missing_keys() -> None:
    with pytest.raises(ValueError, match="missing selection keys"):
        select_top(_frame(5), count=1, seed=7, keys=["nope"])


def test_result_and_severity_validation() -> None:
    frame = _frame(5)
    with pytest.raises(ValueError, match="severity"):
        validate_severity(1.5)
    with pytest.raises(ValueError, match="severity"):
        InjectionResult(
            name="D5",
            severity=0.1,
            realized_severity=1.5,
            affected_units=1,
            affected_rows=1,
            data=frame,
        )
    with pytest.raises(ValueError, match="non-empty"):
        InjectionResult(
            name=" ",
            severity=0.1,
            realized_severity=0.1,
            affected_units=1,
            affected_rows=1,
            data=frame,
        )


class _DummyInjector:
    name = "test_dummy"

    def apply(self, frame: pl.DataFrame, *, severity: float, seed: int) -> InjectionResult:
        return InjectionResult(
            name=self.name,
            severity=severity,
            realized_severity=severity,
            affected_units=0,
            affected_rows=0,
            data=frame,
        )


def test_registry_registers_and_looks_up_injectors() -> None:
    injector = _DummyInjector()
    register(injector)

    assert get("test_dummy") is injector
    assert get("TEST_DUMMY") is injector
    assert "TEST_DUMMY" in available()

    with pytest.raises(ValueError, match="already registered"):
        register(injector)
    with pytest.raises(ValueError, match="unknown injector"):
        get("D_NOT_REAL")
