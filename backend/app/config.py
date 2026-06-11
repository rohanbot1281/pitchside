"""Environment-driven settings."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    football_data_api_key: str = os.getenv("FOOTBALL_DATA_API_KEY", "")
    model: str = os.getenv("PITCHSIDE_MODEL", "claude-sonnet-4-6")
    data_dir: Path = ROOT / "data"
    index_dir: Path = ROOT / "data" / "index"


settings = Settings()
