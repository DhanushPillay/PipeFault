from __future__ import annotations

import math

import pytest

from pipefault.analyze.law import (
    Condition,
    LookupTable,
    fit_law,
    leave_one_defect_out,
    scores,
)


def _condition(
    defect: str,
    severity: float,
    alpha: float,
    gamma: float,
    degradation: float,
    *,
    clean_rmse: float = 10.0,
    family: str | None = None,
) -> Condition:
    return Condition(
        defect=defect,
        severity=severity,
        alpha=alpha,
        gamma=gamma,
        clean_rmse=clean_rmse,
        defect_rmse=clean_rmse * (1.0 + degradation),
        family=family,
    )


def _universal_conditions() -> list[Condition]:
    """Exact universal law, with defect-specific alpha and gamma at each severity.

    The per-defect variation is what makes the severity fallback of the lookup
    table inexact while the law stays exact.
    """
    conditions = []
    for defect_index, defect in enumerate(("D1", "D3", "D5", "D6")):
        for severity_index, severity in enumerate((1, 10, 50)):
            alpha = 0.05 + 0.03 * defect_index + 0.10 * severity_index
            gamma = 0.01 + 0.02 * defect_index + 0.05 * severity_index
            conditions.append(
                _condition(defect, severity, alpha, gamma, 0.02 + 1.5 * alpha + 2.5 * gamma)
            )
    return conditions


def test_fit_recovers_exact_coefficients() -> None:
    conditions = [
        _condition("D1", 1, 0.1, 0.0, 0.5 + 2.0 * 0.1),
        _condition("D1", 5, 0.2, 0.15, 0.5 + 2.0 * 0.2 + 3.0 * 0.15),
        _condition("D3", 10, 0.3, 0.05, 0.5 + 2.0 * 0.3 + 3.0 * 0.05),
        _condition("D5", 25, 0.4, 0.3, 0.5 + 2.0 * 0.4 + 3.0 * 0.3),
        _condition("D6", 50, 0.5, 0.2, 0.5 + 2.0 * 0.5 + 3.0 * 0.2),
    ]

    law = fit_law(conditions)

    assert law.intercept == pytest.approx(0.5)
    assert law.alpha_coefficient == pytest.approx(2.0)
    assert law.gamma_coefficient == pytest.approx(3.0)
    assert scores(law, conditions) == pytest.approx({"mae": 0.0, "r2": 1.0, "n": 5.0}, abs=1e-12)


def test_universal_law_generalizes_to_held_out_defects() -> None:
    result = leave_one_defect_out(_universal_conditions())

    assert result["law"]["mae"] < 1e-9
    assert result["law"]["r2"] == pytest.approx(1.0)
    assert [fold["defect"] for fold in result["folds"]] == ["D1", "D3", "D5", "D6"]


def test_lookup_prefers_exact_then_severity_then_global() -> None:
    conditions = [
        _condition("D1", 10, 0.1, 0.0, 0.20),
        _condition("D1", 25, 0.2, 0.0, 0.40),
        _condition("D5", 10, 0.3, 0.0, 0.30),
    ]
    lookup = LookupTable.build(conditions)

    assert lookup.predict(_condition("D1", 10, 0.0, 0.0, 0.0)) == pytest.approx(0.20)
    assert lookup.predict(_condition("D9", 10, 0.0, 0.0, 0.0)) == pytest.approx(0.25)
    assert lookup.predict(_condition("D9", 99, 0.0, 0.0, 0.0)) == pytest.approx(0.30)


def test_family_lookup_falls_back_to_the_family_severity_mean() -> None:
    conditions = [
        _condition("D7", 10, 0.1, 0.0, 0.10, family="schema"),
        _condition("D6", 10, 0.2, 0.0, 0.30, family="schema"),
    ]
    lookup = LookupTable.build(conditions, key="family")

    assert lookup.predict(_condition("D8", 10, 0.0, 0.0, 0.0, family="schema")) == pytest.approx(
        0.20
    )
    assert lookup.predict(_condition("D8", 99, 0.0, 0.0, 0.0, family="schema")) == pytest.approx(
        0.20
    )


def test_lookup_is_worse_than_the_law_on_a_universal_relationship() -> None:
    result = leave_one_defect_out(_universal_conditions())

    assert result["law"]["mae"] < result["lookup"]["mae"]
    assert result["law"]["mae"] < result["family_lookup"]["mae"]


def test_invalid_conditions_are_rejected() -> None:
    with pytest.raises(ValueError, match="at least 3"):
        fit_law([_condition("D1", 1, 0.1, 0.1, 0.1)] * 2)
    with pytest.raises(ValueError, match="vary"):
        fit_law([_condition("D1", severity, 0.1, 0.1, 0.1) for severity in (1, 5, 10)])
    with pytest.raises(ValueError, match="alpha"):
        _condition("D1", 1, 1.5, 0.1, 0.1)
    with pytest.raises(ValueError, match="gamma"):
        _condition("D1", 1, 0.1, -0.1, 0.1)
    with pytest.raises(ValueError, match="severity"):
        _condition("D1", 0, 0.1, 0.1, 0.1)
    with pytest.raises(ValueError, match="clean_rmse"):
        _condition("D1", 1, 0.1, 0.1, 0.1, clean_rmse=0.0)
    with pytest.raises(ValueError, match="at least one"):
        LookupTable.build([])
    with pytest.raises(ValueError, match="key"):
        LookupTable.build([_condition("D1", 1, 0.1, 0.1, 0.1)], key="dataset")


def test_r2_is_nan_for_constant_targets() -> None:
    pairs = ((1, 0.1, 0.02), (5, 0.4, 0.30), (10, 0.7, 0.11))
    conditions = [_condition("D1", severity, alpha, gamma, 0.2) for severity, alpha, gamma in pairs]
    law = fit_law(conditions)

    assert math.isnan(scores(law, conditions)["r2"])


def test_leave_one_defect_out_needs_two_defects() -> None:
    with pytest.raises(ValueError, match="two defects"):
        leave_one_defect_out([_condition("D1", 1, 0.1, 0.1, 0.1)])
