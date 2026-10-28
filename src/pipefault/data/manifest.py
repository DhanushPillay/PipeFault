from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_manifest(files: Iterable[Path], manifest_path: Path, root: Path) -> None:
    """Write ``<sha256>  <relative path>`` lines for the given files."""
    root = root.resolve()
    entries: list[str] = []
    for path in sorted({p.resolve() for p in files}):
        relative = path.relative_to(root).as_posix()
        entries.append(f"{sha256_file(path)}  {relative}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("\n".join(entries) + "\n", encoding="utf-8")


def read_manifest(manifest_path: Path) -> dict[str, str]:
    """Read a manifest into a mapping of relative path to digest."""
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    return entries


def verify_manifest(manifest_path: Path, root: Path) -> list[str]:
    """Return relative paths whose file is missing or has a different digest."""
    root = root.resolve()
    bad: list[str] = []
    for relative, expected in read_manifest(manifest_path).items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != expected:
            bad.append(relative)
    return bad
