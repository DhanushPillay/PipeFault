param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "data", "audit", "baseline", "lint", "format", "typecheck", "test", "ci", "docker-build", "clean", "help")]
    [string]$Task = "help"
)

switch ($Task) {
    "install" { uv sync --all-extras }
    "data" { uv run pipefault data download }
    "audit" { uv run pipefault data audit }
    "baseline" { uv run pipefault baseline }
    "lint" {
        uv run ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run ruff format --check .
    }
    "format" {
        uv run ruff check --fix .
        uv run ruff format .
    }
    "typecheck" { uv run mypy src }
    "test" { uv run pytest }
    "ci" {
        uv run ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run ruff format --check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run mypy src
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run pytest
    }
    "docker-build" { docker build -t pipefault:dev . }
    "clean" {
        Remove-Item -Recurse -Force .venv, .pytest_cache, .ruff_cache, .mypy_cache, htmlcov, .coverage -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force data/audit, artifacts, mlruns, mlflow.db* -ErrorAction SilentlyContinue
    }
    default {
        Write-Host "make.ps1 install | data | audit | baseline | lint | format | typecheck | test | ci | docker-build | clean"
    }
}
