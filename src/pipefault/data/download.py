from __future__ import annotations

import hashlib
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
MOVIELENS_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"
MOVIELENS_FILES = {
    "links.csv": "8f033867bcb4e6be8792b21468b4fa6e",
    "movies.csv": "0df90835c19151f9d819d0822e190797",
    "ratings.csv": "cf12b74f9ad4b94a011f079e26d4270a",
    "tags.csv": "963bf4fa4de6b8901868fddd3eb54567",
}
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


def md5_file(path: Path) -> str:
    """Return the MD5 hex digest used by GroupLens for file verification."""
    with path.open("rb") as handle:
        return hashlib.file_digest(
            handle, lambda: hashlib.md5(usedforsecurity=False)
        ).hexdigest()


def download_movielens(
    raw_dir: Path,
    *,
    force: bool = False,
    url: str = MOVIELENS_URL,
    checksums: dict[str, str] = MOVIELENS_FILES,
) -> list[Path]:
    """Download ml-32m, extract the four CSVs, and verify every MD5."""
    destination = raw_dir / "movielens"
    archive_path = download_file(
        url, destination / "ml-32m.zip", force=force, timeout=600
    )

    with zipfile.ZipFile(archive_path) as archive:
        members = {Path(name).name: name for name in archive.namelist()}
        missing = sorted(set(checksums) - set(members))
        if missing:
            raise RuntimeError(f"{archive_path} is missing {', '.join(missing)}")

        extracted: list[Path] = []
        for name, expected in checksums.items():
            target = destination / name
            if force or not target.exists():
                safe_extract_member(archive, members[name], destination)
            actual = md5_file(target)
            if actual != expected:
                raise RuntimeError(
                    f"checksum mismatch for {name}: expected {expected}, got {actual}"
                )
            extracted.append(target)

    return [archive_path, *extracted]


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


def raw_files(raw_dir: Path) -> list[Path]:
    """List downloaded files, excluding partial downloads."""
    if not raw_dir.exists():
        return []
    return sorted(
        path
        for path in raw_dir.rglob("*")
        if path.is_file() and not path.name.endswith(".part")
    )
