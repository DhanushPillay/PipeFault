from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipefault.analyze.law import Condition
from pipefault.analyze.report import (
    build_law_report,
    conditions_from_records,
    render_markdown,
    write_report,
)
from pipefault.records import RunRecord, with_annotation


def _record(
    run_id: str,
    *,
    defect: str | None = None,
    severity: float | None = None,
    alpha: float = 0.1,
    gamma: float = 0.05,
    rmse: float = 11.0,
    seed: int = 42,
    status: str = "completed",
    reason: str | None = None,
    annotated: bool = True,
) -> RunRecord:
    metadata = {"defect": defect, "severity": severity} if defect else None
    record = RunRecord(
        run_id=run_id,
        dataset="tlc",
        task="eta-regression",
        model="lightgbm",
        seed=seed,
        config_hash="a" * 64,
        status=status,
        reason=reason,
        metrics={"test_rmse": rmse},
        metadata=metadata,
    )
    if defect is None or status != "completed" or not annotated:
        return record
    return with_annotation(
        record,
        alpha=alpha,
        beta=0.0,
        gamma=gamma,
        matched_rows=100,
        tau_pred=0.5,
        thresholds_hash="b" * 64,
    )


def _conditions() -> list[Condition]:
    conditions = []
    for defect_index, defect in enumerate(("D1", "D3", "D5")):
        for severity_index, severity in enumerate((5, 25)):
            alpha = 0.05 + 0.03 * defect_index + 0.10 * severity_index
            gamma = 0.01 + 0.02 * defect_index + 0.05 * severity_index
            degradation = 0.02 + 1.5 * alpha + 2.5 * gamma
            conditions.append(
                Condition(
                    defect=defect,
                    severity=severity,
                    alpha=alpha,
                    gamma=gamma,
                    clean_rmse=10.0,
                    defect_rmse=10.0 * (1.0 + degradation),
                )
            )
    return conditions


def test_conditions_from_records_pairs_clean_and_defect() -> None:
    clean = _record("tlc-clean-lightgbm-seed42", rmse=10.0)
    defect = _record("tlc-D5-s10-lightgbm-seed42", defect="D5", severity=10, rmse=12.0)

    conditions = conditions_from_records([clean, defect])

    assert len(conditions) == 1
    condition = conditions[0]
    assert condition.defect == "D5"
    assert condition.severity == 10
    assert condition.clean_rmse == 10.0
    assert condition.defect_rmse == 12.0
    assert condition.family == "ingestion"
    assert condition.degradation == pytest.approx(0.2)


def test_conditions_from_records_ignores_failed_runs() -> None:
    clean = _record("clean", rmse=10.0)
    failed = _record("failed", defect="D1", severity=5, status="failed", reason="crash")

    with pytest.raises(ValueError, match="no annotated defect"):
        conditions_from_records([clean, failed])


def test_conditions_from_records_requires_clean_reference_and_annotation() -> None:
    unannotated = _record("defect", defect="D5", severity=10, annotated=False)
    with pytest.raises(ValueError, match="not annotated"):
        conditions_from_records([unannotated])

    annotated = _record("defect", defect="D5", severity=10, rmse=12.0)
    with pytest.raises(ValueError, match="no clean reference"):
        conditions_from_records([annotated])


def test_report_models_and_markdown_share_numbers() -> None:
    report = build_law_report(_conditions())
    markdown = render_markdown(report)

    assert [model["model"] for model in report["models"]] == [
        "corruption_only",
        "lookup_defect",
        "lookup_family",
    ]
    assert report["n_conditions"] == 6
    for model in report["models"]:
        assert f"{float(model['mae']):.4f}" in markdown
        assert f"{float(model['r2']):.4f}" in markdown
    for name, value in report["coefficients"].items():
        assert name in markdown
        assert f"{float(value):.4f}" in markdown
    assert "Gate G2" in markdown


def test_write_report_writes_matching_json_and_markdown(tmp_path: Path) -> None:
    json_path, markdown_path = write_report(tmp_path, _conditions())

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["n_conditions"] == 6
    assert payload["gate_g2"]["passed"] in (True, False)
    assert markdown.startswith("# Damage law v1")
    assert f"{float(payload['gate_g2']['law_mae']):.4f}" in markdown
