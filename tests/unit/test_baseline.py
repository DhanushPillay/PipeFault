from __future__ import annotations

import numpy as np

from pipefault.baseline import regression_metrics


def test_regression_metrics_for_perfect_predictions() -> None:
    y = np.array([1.0, 2.0, 3.0])
    metrics = regression_metrics(y, y)

    assert metrics["rmse"] == 0.0
    assert metrics["mae"] == 0.0
    assert metrics["r2"] == 1.0
    assert metrics["n"] == 3.0


def test_regression_metrics_penalizes_bias() -> None:
    y = np.array([10.0, 20.0, 30.0])
    metrics = regression_metrics(y, y + 2.0)

    assert metrics["rmse"] == 2.0
    assert metrics["mae"] == 2.0
    assert metrics["r2"] < 1.0
