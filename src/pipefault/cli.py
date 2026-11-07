from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from pipefault.baseline import run_tlc_baseline
from pipefault.config import get_settings
from pipefault.data.audit import audit_datasets
from pipefault.data.download import (
    TLC_MONTHS,
    download_movielens,
    download_retail,
    download_tlc,
    raw_files,
)
from pipefault.data.manifest import verify_manifest, write_manifest
from pipefault.features.tlc import DEFAULT_SIZES
from pipefault.logging import configure_logging

app = typer.Typer(no_args_is_help=True, help="Fault-injection benchmark for streaming ML.")
data_app = typer.Typer(no_args_is_help=True, help="Download, audit, and verify datasets.")
app.add_typer(data_app, name="data")
console = Console()


class Dataset(StrEnum):
    all = "all"
    tlc = "tlc"
    movielens = "movielens"
    retail = "retail"


@app.callback()
def main(
    log_json: Annotated[bool, typer.Option("--log-json", help="Emit JSON logs.")] = False,
) -> None:
    configure_logging(json=log_json)


@data_app.command("download")
def download(
    dataset: Annotated[
        Dataset, typer.Option("--dataset", "-d", help="Dataset to download.")
    ] = Dataset.all,
    force: Annotated[bool, typer.Option("--force", help="Redownload existing files.")] = False,
    month: Annotated[
        list[str] | None,
        typer.Option("--month", help="TLC month(s), e.g. 01. Repeatable. Default: all 12."),
    ] = None,
) -> None:
    """Download raw data and write the SHA-256 manifest."""
    settings = get_settings()

    files: list[Path] = []
    try:
        if dataset in (Dataset.all, Dataset.tlc):
            files.extend(
                download_tlc(
                    settings.raw_dir,
                    months=month or TLC_MONTHS,
                    force=force,
                )
            )
        if dataset in (Dataset.all, Dataset.retail):
            files.extend(download_retail(settings.raw_dir, force=force))
        if dataset in (Dataset.all, Dataset.movielens):
            files.extend(download_movielens(settings.raw_dir, force=force))
    except RuntimeError as exc:
        console.print(f"[red]Download failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    collected = sorted(set(files) | set(raw_files(settings.raw_dir)))
    write_manifest(collected, settings.manifest_path, settings.data_dir)
    console.print(f"Wrote {len(collected)} files under [bold]{settings.raw_dir}[/bold]")
    console.print(f"Manifest: [bold]{settings.manifest_path}[/bold]")


@data_app.command("audit")
def audit(
    dataset: Annotated[
        Dataset, typer.Option("--dataset", "-d", help="Dataset to audit.")
    ] = Dataset.all,
) -> None:
    """Measure natural defects in the downloaded data."""
    settings = get_settings()
    names = ["tlc", "movielens", "retail"] if dataset is Dataset.all else [dataset.value]
    results = audit_datasets(names, settings)
    _print_audit(results)
    console.print(f"JSON: [bold]{settings.audit_dir}[/bold]")


@data_app.command("manifest")
def manifest(
    verify: Annotated[bool, typer.Option("--verify", help="Verify existing files.")] = False,
) -> None:
    """Write or verify the SHA-256 manifest."""
    settings = get_settings()
    if verify:
        if not settings.manifest_path.exists():
            console.print(f"[red]No manifest at {settings.manifest_path}[/red]")
            raise typer.Exit(code=1)
        bad = verify_manifest(settings.manifest_path, settings.data_dir)
        if bad:
            console.print("[red]Manifest verification failed:[/red]")
            for name in bad:
                console.print(f"  {name}")
            raise typer.Exit(code=1)
        console.print("[green]Manifest verified.[/green]")
        return

    files = raw_files(settings.raw_dir)
    write_manifest(files, settings.manifest_path, settings.data_dir)
    console.print(f"Wrote manifest with {len(files)} files.")


@app.command("baseline")
def baseline(
    seed: Annotated[int, typer.Option("--seed", help="Random seed.")] = 42,
    train_size: Annotated[int, typer.Option("--train-size", help="Training rows.")] = DEFAULT_SIZES[
        "train"
    ],
    val_size: Annotated[int, typer.Option("--val-size", help="Validation rows.")] = DEFAULT_SIZES[
        "validation"
    ],
    test_size: Annotated[int, typer.Option("--test-size", help="Test rows.")] = DEFAULT_SIZES[
        "test"
    ],
    rounds: Annotated[int, typer.Option("--rounds", help="Maximum boosting rounds.")] = 2000,
    mlflow_enabled: Annotated[
        bool,
        typer.Option("--mlflow/--no-mlflow", help="Log to local MLflow."),
    ] = True,
) -> None:
    """Train and evaluate the clean TLC ETA baseline."""
    settings = get_settings()
    try:
        payload = run_tlc_baseline(
            settings,
            seed=seed,
            sizes={
                "train": train_size,
                "validation": val_size,
                "test": test_size,
            },
            num_boost_round=rounds,
            mlflow_enabled=mlflow_enabled,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Baseline failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _print_baseline(payload)


def _rows_for(name: str, result: dict[str, Any]) -> object:
    return result.get("rows", "-")


def _notes_for(name: str, result: dict[str, Any]) -> str:
    if result.get("status") != "ok":
        return str(result.get("hint", "missing"))
    if name == "tlc":
        return (
            f"duplicates={result.get('duplicate_rows', '-')}, "
            f"invalid_duration={result.get('invalid_duration', '-')}"
        )
    if name == "movielens":
        movies = result.get("movies", {})
        return (
            f"duplicates={result.get('duplicate_user_movie', '-')}, "
            f"invalid_rating={result.get('invalid_rating', '-')}, "
            f"unknown_movie={result.get('unknown_movie', '-')}, "
            f"movies_without_ratings={movies.get('movies_without_ratings', '-')}"
        )
    if name == "retail":
        return (
            f"missing_customer_id={result.get('missing_customer_id', '-')}, "
            f"cancellations={result.get('cancellations', '-')}"
        )
    return ""


def _print_audit(results: dict[str, dict[str, Any]]) -> None:
    table = Table(title="Natural-defect audit")
    table.add_column("Dataset")
    table.add_column("Status")
    table.add_column("Rows", justify="right")
    table.add_column("Notes")
    for name, result in results.items():
        status = str(result.get("status", "?"))
        style = "green" if status == "ok" else "yellow"
        table.add_row(
            name,
            f"[{style}]{status}[/{style}]",
            str(_rows_for(name, result)),
            _notes_for(name, result),
        )
    console.print(table)


def _print_baseline(payload: dict[str, Any]) -> None:
    table = Table(title="TLC ETA baseline")
    table.add_column("Split")
    table.add_column("Model")
    table.add_column("RMSE", justify="right")
    table.add_column("MAE", justify="right")
    table.add_column("R2", justify="right")
    for split in ("validation", "test"):
        for model_name in ("global_median", "zone_median", "lightgbm"):
            metrics = payload["metrics"][split][model_name]
            table.add_row(
                split,
                model_name,
                f"{metrics['rmse']:.3f}",
                f"{metrics['mae']:.3f}",
                f"{metrics['r2']:.4f}",
            )
    console.print(table)
    rows = payload["rows"]
    console.print(
        f"Rows: train={rows['train']:,}, validation={rows['validation']:,}, test={rows['test']:,}"
    )
    console.print(f"Best iteration: {payload['best_iteration']}")
    console.print(f"Artifacts: {payload['artifacts_dir']}")
    if payload.get("mlflow_run_id"):
        console.print(f"MLflow run: {payload['mlflow_run_id']}")


if __name__ == "__main__":
    app()
