from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class PolicyConfig(BaseModel):
    mode: str = "denylist"
    domains: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    cdp_port: int = 9222
    cdp_allow_nat: bool = False
    cdp_timeout_ms: int = 5000
    slow_mo_ms: int = 0

    max_steps_per_run: int = 50
    max_total_runtime_s: int = 120
    min_delay_ms_between_actions: int = 250
    max_extract_chars: int = 20000
    capture_html_snapshot: bool = False

    runs_dir: str = "runs"
    policy: PolicyConfig = Field(default_factory=PolicyConfig)


def load_config(path: Optional[str] = None) -> Settings:
    if not path:
        return Settings()
    cfg_path = Path(path)
    if not cfg_path.exists():
        return Settings()
    data = yaml.safe_load(cfg_path.read_text()) or {}
    return Settings(**data)
