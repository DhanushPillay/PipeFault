from __future__ import annotations

import os
import shutil
import time
import urllib.request
import zipfile
from collections.abc import Iterable
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

TLC_BASE = "https://d37ci6vzurychx.cloudfront.net/trip-data"
TLC_ZONE_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
RETAIL_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
OLIST_DATASET = "olistbr/brazilian-ecommerce"
TLC_MONTHS = tuple(f"{month:02d}" for month in range(1, 13))


def tlc_url(month: str) -> str:
    return f"{TLC_BASE}/yellow_tripdata_2024-{month}.parquet"


def download_file(
    url: str,
    destination: Path,
    *,
    force: bool = False,
    retries: int = 3,
    timeout: int = 180,
) -> Path:
    """Download a URL atomically, with retries and a ``.part`` file."""
    if destination.exists() and not force:
        log.info("download.skip", path=str(destination))
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")

    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "pipefault/0.1 (+https://github.com/)"},
            )
            with (
                urllib.request.urlopen(request, timeout=timeout) as response,
                part.open("wb") as handle,
            ):
                shutil.copyfileobj(response, handle)
            part.replace(destination)
            log.info(
                "download.done",
                url=url,
                path=str(destination),
                bytes=destination.stat().st_size,
            )
            return destination
        except Exception as exc:
            part.unlink(missing_ok=True)
            if attempt == retries:
                raise
            log.warning(
                "download.retry",
                url=url,
                attempt=attempt,
                error=str(exc),
            )
            time.sleep(2**attempt)

    raise RuntimeError(f"download failed after {retries} attempts: {url}")


def safe_extract_member(archive: zipfile.ZipFile, member: str, destination: Path) -> Path:
    """Extract one member under ``destination``, flattening its path."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    target = (destination / Path(member).name).resolve()
    if not target.is_relative_to(destination):
        raise ValueError(f"refusing to extract outside {destination}: {member}")
    with archive.open(member) as source, target.open("wb") as handle:
        shutil.copyfileobj(source, handle)
    return target


def download_tlc(
    raw_dir: Path,
    *,
    months: Iterable[str] = TLC_MONTHS,
    force: bool = False,
) -> list[Path]:
    destination = raw_dir / "tlc"
    files: list[Path] = []
    for month in months:
        files.append(
            download_file(
                tlc_url(month),
                destination / f"yellow_tripdata_2024-{month}.parquet",
                force=force,
            )
        )
    files.append(
        download_file(TLC_ZONE_URL, destination / "taxi_zone_lookup.csv", force=force)
    )
    return files


def download_retail(raw_dir: Path, *, force: bool = False) -> list[Path]:
    destination = raw_dir / "retail"
    archive_path = download_file(
        RETAIL_URL, destination / "online_retail_II.zip", force=force
    )
    workbook = destination / "online_retail_II.xlsx"
    if force or not workbook.exists():
        with zipfile.ZipFile(archive_path) as archive:
            members = [
                name for name in archive.namelist() if name.lower().endswith(".xlsx")
            ]
            if len(members) != 1:
                raise RuntimeError(
                    f"expected one .xlsx in {archive_path}, found {len(members)}"
                )
            workbook = safe_extract_member(archive, members[0], destination)
    return [archive_path, workbook]


def olist_credentials_present() -> bool:
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True
    return (Path.home() / ".kaggle" / "kaggle.json").is_file()


def download_olist(raw_dir: Path, *, force: bool = False) -> list[Path]:
    destination = raw_dir / "olist"
    destination.mkdir(parents=True, exist_ok=True)
    expected = destination / "olist_orders_dataset.csv"
    if expected.exists() and not force:
        log.info("download.skip", path=str(destination))
        return sorted(path for path in destination.rglob("*") if path.is_file())

    if not olist_credentials_present():
        raise RuntimeError(
            "Kaggle credentials not found. Create ~/.kaggle/kaggle.json or set "
            "KAGGLE_USERNAME and KAGGLE_KEY. See https://www.kaggle.com/settings."
        )

    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(
        OLIST_DATASET,
        path=str(destination),
        unzip=True,
        quiet=False,
    )
    files = sorted(path for path in destination.rglob("*") if path.is_file())
    if not expected.exists():
        raise RuntimeError(
            f"Olist download did not produce {expected.name}; found {len(files)} files"
        )
    return files


def raw_files(raw_dir: Path) -> list[Path]:
    """List downloaded files, excluding partial downloads."""
    if not raw_dir.exists():
        return []
    return sorted(
        path
        for path in raw_dir.rglob("*")
        if path.is_file() and not path.name.endswith(".part")
    )
