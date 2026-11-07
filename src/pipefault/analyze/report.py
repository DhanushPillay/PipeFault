"""Pilot law report, generated from run records and never hand-edited."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pipefault.analyze.law import (
    Condition,
    fit_law,
    leave_one_defect_out,
    scores,
)
from pipefault.records import RunRecord

DEFECT_FAMILIES = {
    "D1": "join",
    "D2": "join",
    "D3": "temporal",
    "D4": "temporal",
    "D5": "ingestion",
    "D6": "schema",
    "D7": "partition",
    "D8": "temporal",
}

GATE_G2_MAE_GAIN = 0.10


def _metric(record: RunRecord, name: str = "test_rmse") -> float:
    if not record.metrics or name not in record.metrics:
        raise ValueError(f"run {record.run_id!r} has no {name}")
    return float(record.metrics[name])


def conditions_from_records(records: Sequence[RunRecord]) -> list[Condition]:
    """Pair annotated defect records with their clean reference."""
    completed = [record for record in records if record.status == "completed"]
    cleans: dict[tuple[str, str, int], RunRecord] = {}
    for record in completed:
        metadata = record.metadata or {}
        if metadata.get("defect") is not None:
            continue
        key = (record.dataset, record.model, record.seed)
        if key in cleans:
            raise ValueError(f"duplicate clean reference for {key}")
        cleans[key] = record

    conditions: list[Condition] = []
    for record in completed:
        metadata = record.metadata or {}
        defect = metadata.get("defect")
        if defect is None:
            continue
        if record.alpha is None or record.gamma is None:
            raise ValueError(f"run {record.run_id!r} is not annotated")
        severity = metadata.get("severity")
        if not isinstance(severity, (int, float)) or isinstance(severity, bool):
            raise ValueError(f"run {record.run_id!r} has no numeric severity")
        clean = cleans.get((record.dataset, record.model, record.seed))
        if clean is None:
            raise ValueError(f"run {record.run_id!r} has no clean reference")
        conditions.append(
            Condition(
                defect=str(defect),
                severity=float(severity),
                alpha=record.alpha,
                gamma=record.gamma,
                clean_rmse=_metric(clean),
                defect_rmse=_metric(record),
                family=DEFECT_FAMILIES.get(str(defect)),
            )
        )

    if not conditions:
        raise ValueError("no annotated defect records")
    return sorted(conditions, key=lambda condition: (condition.defect, condition.severity))


def build_law_report(conditions: Sequence[Condition]) -> dict[str, Any]:
    """Fit the law and score it against the lookup baselines on held-out defects."""
    law = fit_law(conditions)
    held_out = leave_one_defect_out(conditions)
    models = [
        {"model": "corruption_only", **held_out["law"]},
        {"model": "lookup_defect", **held_out["lookup"]},
        {"model": "lookup_family", **held_out["family_lookup"]},
    ]
    law_mae = float(models[0]["mae"])
    lookup_mae = min(float(models[1]["mae"]), float(models[2]["mae"]))
    return {
        "n_conditions": len(conditions),
        "defects": sorted({condition.defect for condition in conditions}),
        "coefficients": law.coefficients(),
        "in_sample": scores(law, conditions),
        "models": models,
        "folds": held_out["folds"],
        "gate_g2": {
            "best_lookup_mae": lookup_mae,
            "law_mae": law_mae,
            "required_gain": GATE_G2_MAE_GAIN,
            "gain": 0.0 if lookup_mae == 0 else 1.0 - law_mae / lookup_mae,
            "passed": law_mae <= (1.0 - GATE_G2_MAE_GAIN) * lookup_mae,
        },
    }


def _number(value: float) -> str:
    return "n/a" if value != value else f"{value:.4f}"


def render_markdown(report: dict[str, Any]) -> str:
    """Render the report with every value interpolated from ``report``."""
    lines = [
        "# Damage law v1",
        "",
        (
            f"Conditions: {report['n_conditions']} across "
            f"{len(report['defects'])} defects "
            f"({', '.join(report['defects'])})."
        ),
        "",
        "## Held-out defects",
        "",
        "| Model | MAE | R2 | n |",
        "|---|---:|---:|---:|",
    ]
    for model in report["models"]:
        lines.append(
            f"| {model['model']} | {_number(float(model['mae']))} "
            f"| {_number(float(model['r2']))} | {int(model['n'])} |"
        )
    coefficients = report["coefficients"]
    lines += [
        "",
        "## Law coefficients",
        "",
        "| Term | Coefficient |",
        "|---|---:|",
        f"| intercept | {_number(float(coefficients['intercept']))} |",
        f"| alpha | {_number(float(coefficients['alpha']))} |",
        f"| gamma | {_number(float(coefficients['gamma']))} |",
        "",
        "## Leave-one-defect-out",
        "",
        "| Held-out defect | Law MAE | Lookup MAE |",
        "|---|---:|---:|",
    ]
    for fold in report["folds"]:
        lines.append(
            f"| {fold['defect']} | {_number(float(fold['law_mae']))} "
            f"| {_number(float(fold['lookup_mae']))} |"
        )
    gate = report["gate_g2"]
    lines += [
        "",
        "## Gate G2",
        "",
        (
            f"Law MAE {_number(float(gate['law_mae']))} vs best lookup "
            f"{_number(float(gate['best_lookup_mae']))}; gain "
            f"{_number(float(gate['gain']))} against a required "
            f"{_number(float(gate['required_gain']))}. "
            f"Passed: {'yes' if gate['passed'] else 'no'}."
        ),
        "",
    ]
    return "\n".join(lines)


def write_report(directory: Path, conditions: Sequence[Condition]) -> tuple[Path, Path]:
    """Write ``pilot.json`` and ``pilot.md`` from the same report object."""
    report = build_law_report(conditions)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "pilot.json"
    markdown_path = directory / "pilot.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
