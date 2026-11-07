"""Point-in-time joins for versioned dimensions.

The clean path attaches the version that was effective when the fact happened.
The D3 defect uses ``latest_lookup`` instead, which collapses the dimension to
one version per key.
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

_ROW = "_pf_asof_row"


def build_versions(
    frame: pl.DataFrame,
    *,
    key: str,
    date_column: str,
    value_columns: Sequence[str],
) -> pl.DataFrame:
    """One row per key and date, sorted for an as-of join."""
    required = [key, date_column, *value_columns]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"missing version columns: {', '.join(missing)}")

    return (
        frame.select(required)
        .drop_nulls([key, date_column])
        .unique(subset=[key, date_column], keep="first", maintain_order=True)
        .sort([key, date_column])
    )


def asof_lookup(
    facts: pl.DataFrame,
    versions: pl.DataFrame,
    *,
    key: str,
    fact_date: str,
    version_date: str,
    value_columns: Sequence[str],
) -> pl.DataFrame:
    """Attach the latest version dated on or before each fact's date.

    A version dated after the fact is never visible, so the join cannot leak
    the future. Fact row order is preserved.
    """
    left = facts.with_row_index(_ROW).sort(fact_date)
    right = versions.sort([key, version_date])
    joined = left.join_asof(
        right,
        left_on=fact_date,
        right_on=version_date,
        by=key,
        strategy="backward",
        suffix="_version",
        check_sortedness=False,
    )
    return joined.sort(_ROW).drop(_ROW)


def latest_lookup(
    versions: pl.DataFrame,
    *,
    key: str,
    version_date: str,
    value_columns: Sequence[str],
) -> pl.DataFrame:
    """Collapse the dimension to the newest version of each key."""
    ordered = versions.sort([key, version_date])
    return (
        ordered.group_by(key)
        .agg(
            [pl.col(column).last().alias(column) for column in value_columns]
            + [pl.col(version_date).last().alias(version_date)]
        )
        .sort(key)
    )
