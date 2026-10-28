from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime paths and experiment defaults.

    Environment variables use the ``PIPEFAULT_`` prefix, for example
    ``PIPEFAULT_DATA_DIR=D:/pipefault-data``.
    """

    model_config = SettingsConfigDict(
        env_prefix="PIPEFAULT_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    seed: int = 42
    log_json: bool = False

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def audit_dir(self) -> Path:
        return self.data_dir / "audit"

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.sha256"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
