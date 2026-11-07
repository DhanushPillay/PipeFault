"""Paired-run annotation: match predictions on provenance id.

Alpha is an oracle quantity: it measures decision displacement on rows that
survive in both runs. Rows added or dropped by the operator enter gamma, not
alpha.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import polars as pl

from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN

ANNOTATION_VERSION = "1"
TAU_MULTIPLIER = 0.1
EPSILON = 1e-12
_REQUIRED = (PROVENANCE_COLUMN, OCCURRENCE_COLUMN, "y", "yhat")


@dataclass(frozen=True)
class MatchedPredictions:
    """Rows present in both runs, one row per provenance id."""

    rows: pl.DataFrame
    clean_rows: int
    defect_rows: int
    matched_rows: int
    unmatched_clean: int
    unmatched_defect: int

    @property
    def unmatched_clean_fraction(self) -> float:
        return self.unmatched_clean / self.clean_rows if self.clean_rows else 0.0

    @property
    def unmatched_defect_fraction(self) -> float:
        return self.unmatched_defect / self.defect_rows if self.defect_rows else 0.0


@dataclass(frozen=True)
class Annotation:
    """Alpha, beta, gamma, and the silence index for one paired condition."""

    alpha: float
    beta: float
    gamma: float
    silence_index: float
    tau_pred: float
    matched_rows: int
    clean_rows: int
    defect_rows: int
    unmatched_clean: int
    unmatched_defect: int
    version: str = ANNOTATION_VERSION


def _validate(frame: pl.DataFrame, label: str) -> None:
    missing = [column for column in _REQUIRED if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} predictions missing columns: {', '.join(missing)}")
    if frame.height == 0:
        raise ValueError(f"{label} predictions are empty")


def _first_occurrence(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.unique(subset=[PROVENANCE_COLUMN], keep="first")


def match_predictions(clean: pl.DataFrame, defect: pl.DataFrame) -> MatchedPredictions:
    """Inner-join predictions on provenance id, keeping the first occurrence.

    Duplicate copies share an id. Only the first occurrence of each id is used,
    so replay duplicates cannot inflate the matched count.
    """
    _validate(clean, "clean")
    _validate(defect, "defect")
    clean_first = _first_occurrence(clean)
    defect_first = _first_occurrence(defect)
    rows = clean_first.select([PROVENANCE_COLUMN, "y", "yhat"]).join(
        defect_first.select([PROVENANCE_COLUMN, "y", "yhat"]),
        on=PROVENANCE_COLUMN,
        how="inner",
        suffix="_defect",
    )
    if rows.height == 0:
        raise ValueError("no matched rows between clean and defect predictions")

    return MatchedPredictions(
        rows=rows,
        clean_rows=clean.height,
        defect_rows=defect.height,
        matched_rows=rows.height,
        unmatched_clean=clean_first.height - rows.height,
        unmatched_defect=defect_first.height - rows.height,
    )


def freeze_tau(clean_validation: pl.DataFrame, *, multiplier: float = TAU_MULTIPLIER) -> float:
    """Freeze ``tau_pred`` from clean validation predictions only."""
    _validate(clean_validation, "clean validation")
    if multiplier <= 0:
        raise ValueError("multiplier must be positive")
    spread = clean_validation["yhat"].std()
    if spread is None:
        raise ValueError("clean validation yhat has no numeric spread")
    tau = multiplier * float(cast(float, spread))
    if tau <= 0:
        raise ValueError("tau_pred is zero; clean validation predictions are constant")
    return tau


def decision_displacement(matched: MatchedPredictions, *, tau_pred: float) -> float:
    """Alpha: share of matched rows whose prediction moved past ``tau_pred``."""
    if tau_pred <= 0:
        raise ValueError("tau_pred must be positive")
    moved = (matched.rows["yhat_defect"] - matched.rows["yhat"]).abs() > tau_pred
    return float(cast(float, moved.mean()))


def coverage_displacement(clean: pl.DataFrame, defect: pl.DataFrame) -> float:
    """Gamma: relative change in retained row count, clipped to [0, 1]."""
    _validate(clean, "clean")
    _validate(defect, "defect")
    return min(1.0, abs(defect.height - clean.height) / clean.height)


def annotate_pair(
    clean: pl.DataFrame,
    defect: pl.DataFrame,
    *,
    tau_pred: float,
    beta: float = 0.0,
) -> Annotation:
    """Compute alpha, gamma, and the silence index for one split."""
    if not 0.0 <= beta <= 1.0:
        raise ValueError("beta must be in [0, 1]")
    matched = match_predictions(clean, defect)
    alpha = decision_displacement(matched, tau_pred=tau_pred)
    gamma = coverage_displacement(clean, defect)
    total = alpha + beta + gamma
    silence = alpha / (total + EPSILON) if total > 0 else 0.0
    return Annotation(
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        silence_index=min(1.0, max(0.0, silence)),
        tau_pred=tau_pred,
        matched_rows=matched.matched_rows,
        clean_rows=matched.clean_rows,
        defect_rows=matched.defect_rows,
        unmatched_clean=matched.unmatched_clean,
        unmatched_defect=matched.unmatched_defect,
    )
