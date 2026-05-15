"""Project-wide configuration via pydantic-settings.

A single ``settings`` singleton exposes paths, the deterministic master seed,
and credentials read from ``.env`` (never logged, never committed).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Master deterministic seed (today, YYYYMMDD).
    seed: int = 20260514

    # PERLA ordinal scale (1 = lightest, 11 = darkest).
    perla_min: int = 1
    perla_max: int = 11

    # Hugging Face Inference API.
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")
    hf_user_agent: str = Field(default="apd-audit/0.1", alias="HF_USER_AGENT")

    # -- path properties (always absolute, anchored at the project root) ----

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    @property
    def data_raw(self) -> Path:
        return _PROJECT_ROOT / "data" / "raw"

    @property
    def data_interim(self) -> Path:
        return _PROJECT_ROOT / "data" / "interim"

    @property
    def data_processed(self) -> Path:
        return _PROJECT_ROOT / "data" / "processed"

    @property
    def images_dir(self) -> Path:
        return _PROJECT_ROOT / "images"

    @property
    def results_tables(self) -> Path:
        return _PROJECT_ROOT / "results" / "tables"

    @property
    def results_figures(self) -> Path:
        return _PROJECT_ROOT / "results" / "figures"

    @property
    def perla_tones(self) -> list[int]:
        return list(range(self.perla_min, self.perla_max + 1))


settings = Settings()
