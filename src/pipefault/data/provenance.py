"""Stable row identity for paired clean and defect runs.

The id is derived from the dataset name, the raw file name, and the row's
position in that file. It is assigned once, before cleaning, and must survive
every later filter, join, and split. Duplicate copies of a row share the id;
``pf_occurrence`` tells them apart.
"""

from __future__ import annotations

import polars as pl

PROVENANCE_COLUMN = "pf_row_id"
OCCURRENCE_COLUMN = "pf_occurrence"
_ROW_INDEX = "pf_row_index"


def add_provenance(
    frame: pl.DataFrame,
    *,
    dataset: str,
    file: str,
    seed: int = 42,
) -> pl.DataFrame:
    """Attach a deterministic id to every current row of ``frame``."""
    if not dataset or not file:
        raise ValueError("dataset and file must be non-empty")

    return (
        frame.with_row_index(_ROW_INDEX)
        .with_columns(
            pl.struct(
                [
                    pl.lit(dataset).alias("dataset"),
                    pl.lit(file).alias("file"),
                    pl.col(_ROW_INDEX).alias("row_index"),
                ]
            )
            .hash(seed=seed)
            .cast(pl.UInt64)
            .alias(PROVENANCE_COLUMN)
        )
        .with_columns(pl.lit(0, dtype=pl.UInt32).alias(OCCURRENCE_COLUMN))
        .drop(_ROW_INDEX)
    )


def add_occurrence(frame: pl.DataFrame) -> pl.DataFrame:
    """Number duplicate copies of each provenance id from zero."""
    if PROVENANCE_COLUMN not in frame.columns:
        raise ValueError(f"missing {PROVENANCE_COLUMN}; call add_provenance first")

    return frame.with_columns(
        (pl.col(PROVENANCE_COLUMN).cum_count().over(PROVENANCE_COLUMN) - 1)
        .cast(pl.UInt32)
        .alias(OCCURRENCE_COLUMN)
    )
