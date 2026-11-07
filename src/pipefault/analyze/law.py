"""Damage law v1: relative degradation from decision and coverage displacement."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass(frozen=True)
class Condition:
    """One annotated clean/defect pair on the same split."""

    defect: str
    severity: float
    alpha: float
    gamma: float
    clean_rmse: float
    defect_rmse: float
    family: str | None = None

    def __post_init__(self) -> None:
        if not self.defect.strip():
            raise ValueError("defect must be a non-empty string")
        if not np.isfinite(self.severity) or self.severity <= 0:
            raise ValueError("severity must be finite and positive")
        for name in ("alpha", "gamma"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        for name in ("clean_rmse", "defect_rmse"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

    @property
    def family_key(self) -> str:
        return self.family or self.defect

    @property
    def degradation(self) -> float:
        return (self.defect_rmse - self.clean_rmse) / self.clean_rmse


@dataclass(frozen=True)
class LawModel:
    """Ordinary least squares on an intercept, alpha, and gamma."""

    intercept: float
    alpha_coefficient: float
    gamma_coefficient: float

    def predict(self, condition: Condition) -> float:
        return (
            self.intercept
            + self.alpha_coefficient * condition.alpha
            + self.gamma_coefficient * condition.gamma
        )

    def coefficients(self) -> dict[str, float]:
        return {
            "intercept": self.intercept,
            "alpha": self.alpha_coefficient,
            "gamma": self.gamma_coefficient,
        }


class Predictor(Protocol):
    def predict(self, condition: Condition) -> float: ...


def fit_law(conditions: Sequence[Condition]) -> LawModel:
    """Fit the law. Raises when the features cannot identify three coefficients."""
    if len(conditions) < 3:
        raise ValueError("law fit needs at least 3 conditions")
    matrix = np.asarray(
        [[1.0, condition.alpha, condition.gamma] for condition in conditions],
        dtype=np.float64,
    )
    target = np.asarray([condition.degradation for condition in conditions], dtype=np.float64)
    if not np.isfinite(target).all():
        raise ValueError("degradation must be finite")
    if np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise ValueError("alpha and gamma do not vary enough to identify the law")
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    return LawModel(
        intercept=float(solution[0]),
        alpha_coefficient=float(solution[1]),
        gamma_coefficient=float(solution[2]),
    )


@dataclass(frozen=True)
class LookupTable:
    """Per-defect or per-family lookup with severity and global fallbacks."""

    group_means: dict[tuple[str, float], float]
    severity_means: dict[float, float]
    global_mean: float
    key: str = "defect"

    def __post_init__(self) -> None:
        if self.key not in {"defect", "family"}:
            raise ValueError("key must be 'defect' or 'family'")

    @classmethod
    def build(cls, conditions: Sequence[Condition], *, key: str = "defect") -> LookupTable:
        if not conditions:
            raise ValueError("lookup needs at least one condition")
        if key not in {"defect", "family"}:
            raise ValueError("key must be 'defect' or 'family'")
        grouped: dict[tuple[str, float], list[float]] = {}
        by_severity: dict[float, list[float]] = {}
        everything: list[float] = []
        for condition in conditions:
            group = condition.family_key if key == "family" else condition.defect
            severity = float(condition.severity)
            value = condition.degradation
            grouped.setdefault((group, severity), []).append(value)
            by_severity.setdefault(severity, []).append(value)
            everything.append(value)
        return cls(
            group_means={group: float(np.mean(values)) for group, values in grouped.items()},
            severity_means={
                severity: float(np.mean(values)) for severity, values in by_severity.items()
            },
            global_mean=float(np.mean(everything)),
            key=key,
        )

    def predict(self, condition: Condition) -> float:
        group = condition.family_key if self.key == "family" else condition.defect
        exact = self.group_means.get((group, float(condition.severity)))
        if exact is not None:
            return exact
        severity_mean = self.severity_means.get(float(condition.severity))
        if severity_mean is not None:
            return severity_mean
        return self.global_mean


def scores(predictor: Predictor, conditions: Sequence[Condition]) -> dict[str, float]:
    """Mean absolute error and R2 of degradation predictions."""
    if not conditions:
        raise ValueError("scoring needs at least one condition")
    truth = np.asarray([condition.degradation for condition in conditions], dtype=np.float64)
    predicted = np.asarray([predictor.predict(condition) for condition in conditions])
    return _score_arrays(predicted, truth)


def leave_one_defect_out(conditions: Sequence[Condition]) -> dict[str, Any]:
    """Fit on all but one defect, predict the held-out defect, report both models."""
    defects = sorted({condition.defect for condition in conditions})
    if len(defects) < 2:
        raise ValueError("leave-one-defect-out needs at least two defects")
    law_truth: list[float] = []
    law_predicted: list[float] = []
    lookup_predicted: list[float] = []
    family_predicted: list[float] = []
    folds: list[dict[str, float | str]] = []
    for defect in defects:
        train = [condition for condition in conditions if condition.defect != defect]
        test = [condition for condition in conditions if condition.defect == defect]
        law = fit_law(train)
        lookup = LookupTable.build(train)
        family = LookupTable.build(train, key="family")
        fold_truth = np.asarray([condition.degradation for condition in test])
        fold_law = np.asarray([law.predict(condition) for condition in test])
        law_truth.extend(fold_truth.tolist())
        law_predicted.extend(fold_law.tolist())
        lookup_predicted.extend([lookup.predict(condition) for condition in test])
        family_predicted.extend([family.predict(condition) for condition in test])
        folds.append(
            {
                "defect": defect,
                "law_mae": float(np.mean(np.abs(fold_truth - fold_law))),
                "lookup_mae": float(
                    np.mean(
                        [
                            abs(condition.degradation - lookup.predict(condition))
                            for condition in test
                        ]
                    )
                ),
            }
        )
    truth = np.asarray(law_truth)
    return {
        "law": _score_arrays(np.asarray(law_predicted), truth),
        "lookup": _score_arrays(np.asarray(lookup_predicted), truth),
        "family_lookup": _score_arrays(np.asarray(family_predicted), truth),
        "folds": folds,
    }


def _score_arrays(predicted: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    residual = truth - predicted
    centered = truth - truth.mean()
    total = float(np.sum(centered**2))
    constant = bool(np.ptp(truth) == 0.0)
    return {
        "mae": float(np.mean(np.abs(residual))),
        "r2": float("nan") if constant else 1.0 - float(np.sum(residual**2)) / total,
        "n": float(truth.size),
    }
