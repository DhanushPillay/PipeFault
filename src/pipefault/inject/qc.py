"""Perturb-then-verify checks for the pilot injectors."""

from __future__ import annotations

from typing import Final, NoReturn

import polars as pl

from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN
from pipefault.inject.base import InjectionResult

TOLERANCE: Final = 0.02


def _fail(message: str) -> NoReturn:
    raise RuntimeError(f"injection QC failed: {message}")


def _changed_rows(original: pl.DataFrame, data: pl.DataFrame, columns: list[str]) -> int:
    joined = original.select([PROVENANCE_COLUMN, *columns]).join(
        data.select([PROVENANCE_COLUMN, *columns]),
        on=PROVENANCE_COLUMN,
        how="inner",
        suffix="_new",
    )
    if joined.height != original.height:
        _fail("provenance ids do not match the input frame")
    moved = pl.any_horizontal(
        [(pl.col(column) != pl.col(f"{column}_new")).fill_null(False) for column in columns]
    )
    return int(joined.filter(moved).height)


def verify_injection(
    original: pl.DataFrame,
    result: InjectionResult,
    *,
    tolerance: float = TOLERANCE,
) -> None:
    """Recompute the expected effect of an injection and fail on mismatch."""
    if result.data.columns != original.columns:
        _fail("column set changed")
    if result.data.schema != original.schema:
        _fail("schema changed")
    if not set(original[PROVENANCE_COLUMN]).issubset(set(result.data[PROVENANCE_COLUMN])):
        _fail("input rows were dropped")

    height_delta = result.data.height - original.height
    if result.name == "D1":
        dimension_rows = result.details.get("dimension_rows")
        if not isinstance(dimension_rows, int) or dimension_rows <= 0:
            _fail("missing dimension row count")
        if abs(result.realized_severity - result.affected_units / dimension_rows) > 1e-9:
            _fail("realized severity disagrees with the duplicated key count")
    elif result.name in {"D3", "D6"}:
        if abs(result.realized_severity - result.affected_rows / original.height) > 1e-9:
            _fail("realized severity disagrees with the changed row count")
    elif abs(result.realized_severity - max(0.0, height_delta) / original.height) > 1e-9:
        _fail("realized severity disagrees with the row delta")
    if result.realized_severity > result.severity + tolerance:
        _fail("realized severity exceeds the requested severity")

    if result.name == "D5":
        if height_delta != result.affected_rows:
            _fail("duplicate row count mismatch")
        if result.affected_rows != result.affected_units:
            _fail("duplicate row and unit counts differ")
        per_id = result.data.group_by(PROVENANCE_COLUMN).len()
        duplicated = per_id.filter(pl.col("len") == 2).height
        if duplicated != result.affected_rows:
            _fail("duplicated id count mismatch")
        if per_id["len"].max() != 2:
            _fail("unexpected duplicate depth")
    elif result.name == "D1":
        if result.data.height <= original.height:
            _fail("fanout added no rows")
        if height_delta != result.affected_rows:
            _fail("fanout row count mismatch")
        per_id = result.data.group_by(PROVENANCE_COLUMN).len()
        if per_id.filter(pl.col("len") == 2).height != result.affected_rows:
            _fail("fanout duplicated id count mismatch")
        if abs(result.realized_severity - result.severity) > tolerance:
            _fail("fanout severity outside tolerance")
    elif result.name == "D6":
        column = str(result.details.get("column", ""))
        if not column:
            _fail("missing coercion column in details")
        changed = _changed_rows(original, result.data, [column])
        if changed != result.affected_rows:
            _fail("changed value count mismatch")
        others = [
            name
            for name in original.columns
            if name not in {PROVENANCE_COLUMN, OCCURRENCE_COLUMN, column}
        ]
        if _changed_rows(original, result.data, others) != 0:
            _fail("coercion changed an unrelated column")
    elif result.name == "D3":
        if result.data.height != original.height:
            _fail("as-of join changed the row count")
        columns = result.details.get("value_columns", [])
        if not isinstance(columns, (list, tuple)) or not columns:
            _fail("missing value columns in details")
        columns = [str(name) for name in columns]
        if _changed_rows(original, result.data, columns) != result.affected_rows:
            _fail("changed stat count mismatch")
        others = [
            name
            for name in original.columns
            if name not in {PROVENANCE_COLUMN, OCCURRENCE_COLUMN, *columns}
        ]
        if _changed_rows(original, result.data, others) != 0:
            _fail("as-of join changed an unrelated column")
    else:
        _fail(f"no QC defined for {result.name!r}")
