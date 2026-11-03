from __future__ import annotations

from pathlib import Path

from pipefault.data.manifest import (
    read_manifest,
    sha256_file,
    verify_manifest,
    write_manifest,
)


def test_manifest_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    file = root / "a.txt"
    file.write_text("hello", encoding="utf-8")
    manifest = root / "manifest.sha256"

    write_manifest([file], manifest, root)

    assert read_manifest(manifest) == {"a.txt": sha256_file(file)}
    assert verify_manifest(manifest, root) == []

    file.write_text("changed", encoding="utf-8")
    assert verify_manifest(manifest, root) == ["a.txt"]


def test_manifest_ignores_blank_lines(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.sha256"
    manifest.write_text("\n\n", encoding="utf-8")
    assert read_manifest(manifest) == {}
