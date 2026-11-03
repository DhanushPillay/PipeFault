"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """A temporary PIPEFAULT_DATA_DIR with the expected layout."""
    data_dir = tmp_path / "data"
    (data_dir / "raw").mkdir(parents=True)
    (data_dir / "audit").mkdir(parents=True)
    os.environ["PIPEFAULT_DATA_DIR"] = str(data_dir)
    return data_dir
