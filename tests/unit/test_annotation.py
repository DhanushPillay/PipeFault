from __future__ import annotations

import polars as pl
import pytest

from pipefault.analyze.annotation import (
    annotate_pair,
    coverage_displacement,
    decision_displacement,
    freeze_tau,
    match_predictions,
)
from pipefault.data.provenance import OCCURRENCE_COLUMN, PROVENANCE_COLUMN


def _predictions(
    ids: list[int],
    yhat: list[float],
    *,
    occurrences: list[int] | None = None,
    y: list[float] | None = None,
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            PROVENANCE_COLUMN: ids,
            OCCURRENCE_COLUMN: occurrences or [0] * len(ids),
            "y": y or [0.0] * len(ids),
            "yhat": yhat,
        }
    )


def test_matcher_reports_exact_matches_and_drops() -> None:
    clean = _predictions([1, 2, 3, 4, 5], [1.0, 2.0, 3.0, 4.0, 5.0])
    defect = _predictions([1, 2, 3, 4], [1.0, 2.0, 3.0, 4.0])

    matched = match_predictions(clean, defect)

    assert matched.matched_rows == 4
    assert matched.unmatched_clean == 1
    assert matched.unmatched_defect == 0
    assert matched.unmatched_clean_fraction == pytest.approx(0.2)
    assert matched.unmatched_defect_fraction == 0.0


def test_matcher_uses_the_first_occurrence_of_each_id() -> None:
    clean = _predictions([1, 1, 2], [1.0, 9.0, 2.0], occurrences=[0, 1, 0])
    defect = _predictions([1, 2], [1.5, 2.5])

    matched = match_predictions(clean, defect)

    assert matched.matched_rows == 2
    assert matched.unmatched_clean == 0
    assert matched.rows.filter(pl.col(PROVENANCE_COLUMN) == 1)["yhat"].to_list() == [1.0]


def test_matcher_reports_added_rows_as_unmatched_defect() -> None:
    clean = _predictions([1, 2], [1.0, 2.0])
    defect = _predictions([1, 2, 3], [1.0, 2.0, 3.0])

    matched = match_predictions(clean, defect)

    assert matched.unmatched_clean == 0
    assert matched.unmatched_defect == 1
    assert matched.unmatched_defect_fraction == pytest.approx(1 / 3)


def test_matcher_rejects_bad_frames() -> None:
    clean = _predictions([1, 2], [1.0, 2.0])

    with pytest.raises(ValueError, match="missing columns"):
        match_predictions(clean.drop("yhat"), clean)
    with pytest.raises(ValueError, match="empty"):
        match_predictions(clean.head(0), clean)
    with pytest.raises(ValueError, match="no matched rows"):
        match_predictions(clean, _predictions([9], [1.0]))


def test_freeze_tau_uses_clean_validation_spread() -> None:
    validation = _predictions([1, 2, 3, 4, 5], [1.0, 2.0, 3.0, 4.0, 5.0])

    tau = freeze_tau(validation)

    assert tau == pytest.approx(0.1 * validation["yhat"].std())
    assert freeze_tau(validation, multiplier=0.2) == pytest.approx(2 * tau)


def test_freeze_tau_rejects_constant_and_invalid_input() -> None:
    constant = _predictions([1, 2], [3.0, 3.0])

    with pytest.raises(ValueError, match="constant"):
        freeze_tau(constant)
    with pytest.raises(ValueError, match="positive"):
        freeze_tau(constant, multiplier=0.0)


def test_alpha_recovers_a_known_decision_shift() -> None:
    clean = _predictions([1, 2, 3, 4], [0.0, 0.0, 0.0, 0.0])
    defect = _predictions([1, 2, 3, 4], [0.0, 0.5, 0.0, 0.05])

    matched = match_predictions(clean, defect)
    alpha = decision_displacement(matched, tau_pred=0.1)

    assert alpha == pytest.approx(0.25)


def test_alpha_ignores_added_rows() -> None:
    clean = _predictions([1, 2, 3, 4], [0.0, 0.0, 0.0, 0.0])
    defect = _predictions([1, 2, 3, 4, 99], [0.0, 0.5, 0.0, 0.0, 99.0])

    annotation = annotate_pair(clean, defect, tau_pred=0.1)

    assert annotation.alpha == pytest.approx(0.25)
    assert annotation.matched_rows == 4


def test_gamma_is_the_relative_row_change() -> None:
    clean = _predictions([1, 2, 3, 4], [0.0] * 4)

    assert coverage_displacement(
        clean, _predictions([1, 2, 3, 4, 5, 6], [0.0] * 6)
    ) == pytest.approx(0.5)
    assert coverage_displacement(clean, _predictions([1, 2], [0.0] * 2)) == pytest.approx(0.5)


def test_clean_clean_annotation_is_zero() -> None:
    clean = _predictions([1, 2, 3], [1.0, 2.0, 3.0])

    annotation = annotate_pair(clean, clean, tau_pred=0.1)

    assert annotation.alpha == 0.0
    assert annotation.beta == 0.0
    assert annotation.gamma == 0.0
    assert annotation.silence_index == 0.0


def test_annotation_rejects_invalid_parameters() -> None:
    clean = _predictions([1, 2], [0.0, 1.0])

    with pytest.raises(ValueError, match="beta"):
        annotate_pair(clean, clean, tau_pred=0.1, beta=1.5)
    with pytest.raises(ValueError, match="tau_pred"):
        annotate_pair(clean, clean, tau_pred=0.0)
