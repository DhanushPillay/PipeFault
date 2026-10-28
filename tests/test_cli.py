from __future__ import annotations

from typer.testing import CliRunner

from pipefault.cli import app


def test_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "data" in result.stdout


def test_data_help() -> None:
    result = CliRunner().invoke(app, ["data", "--help"])
    assert result.exit_code == 0
    assert "download" in result.stdout
    assert "audit" in result.stdout
