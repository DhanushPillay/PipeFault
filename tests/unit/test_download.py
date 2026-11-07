from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from pipefault.data.download import (
    download_file,
    download_movielens,
    safe_extract_member,
    tlc_url,
)


def test_tlc_url_is_pinned_to_2024() -> None:
    assert tlc_url("01").endswith("yellow_tripdata_2024-01.parquet")


def test_download_file_from_file_uri(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    destination = tmp_path / "nested" / "destination.txt"

    result = download_file(source.as_uri(), destination)

    assert result.read_text(encoding="utf-8") == "hello"


def test_safe_extract_member_flattens_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../evil.txt", "x")

    with zipfile.ZipFile(archive_path) as archive:
        target = safe_extract_member(archive, "../evil.txt", tmp_path / "out")

    assert target == (tmp_path / "out" / "evil.txt").resolve()


def _movielens_archive(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    payload = {
        "links.csv": b"movieId,imdbId,tmdbId\n1,2,3\n",
        "movies.csv": b"movieId,title,genres\n1,Toy Story (1995),Animation\n",
        "ratings.csv": b"userId,movieId,rating,timestamp\n1,1,4.0,100\n",
        "tags.csv": b"userId,movieId,tag,timestamp\n1,1,fun,100\n",
    }
    archive_path = tmp_path / "ml-32m.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for name, data in payload.items():
            archive.writestr(f"ml-32m/{name}", data)
    checksums = {
        name: hashlib.md5(data, usedforsecurity=False).hexdigest() for name, data in payload.items()
    }
    return archive_path, checksums


def test_movielens_download_extracts_and_verifies(tmp_path: Path) -> None:
    archive_path, checksums = _movielens_archive(tmp_path)

    files = download_movielens(
        tmp_path / "raw",
        url=archive_path.as_uri(),
        checksums=checksums,
    )

    assert {path.name for path in files} == {"ml-32m.zip", *checksums}
    assert (tmp_path / "raw" / "movielens" / "ratings.csv").is_file()


def test_movielens_download_rejects_bad_checksum(tmp_path: Path) -> None:
    archive_path, checksums = _movielens_archive(tmp_path)
    checksums["ratings.csv"] = "0" * 32

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        download_movielens(
            tmp_path / "raw",
            url=archive_path.as_uri(),
            checksums=checksums,
        )
