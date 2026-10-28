from __future__ import annotations

import zipfile
from pathlib import Path

from pipefault.data.download import download_file, safe_extract_member, tlc_url


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
