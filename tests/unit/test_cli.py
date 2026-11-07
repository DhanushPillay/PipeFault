from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pipefault.cli import Dataset, app


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "pilot.yaml"
    path.write_text("name: pilot\nseeds: [42, 7]\n", encoding="utf-8")
    return path


def test_movielens_dataset_is_available() -> None:
    assert Dataset.movielens.value == "movielens"


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "data" in result.stdout


def test_data_help() -> None:
    result = CliRunner().invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    assert "download" in result.stdout
    assert "audit" in result.stdout


def test_run_dry_run_is_stable(tmp_path: Path) -> None:
    config = _config(tmp_path)
    runner = CliRunner()

    first = runner.invoke(app, ["run", "--config", str(config), "--dry-run"])
    second = runner.invoke(app, ["run", "--config", str(config), "--dry-run"])

    assert first.exit_code == 0, first.stdout
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload["run_id"].startswith("run-")
    assert len(payload["config_hash"]) == 64
    assert payload["config"] == {"name": "pilot", "seeds": [42, 7]}


def test_run_without_dry_run_reports_p1(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["run", "--config", str(_config(tmp_path))])

    assert result.exit_code == 2
    assert "P1" in result.stdout


def test_annotate_and_law_help() -> None:
    runner = CliRunner()
    for command in ("annotate", "law"):
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, result.stdout
