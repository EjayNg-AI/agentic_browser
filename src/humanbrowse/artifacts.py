from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from dateutil import parser as date_parser


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{uuid4().hex[:8]}"


@dataclass
class RunArtifacts:
    run_id: str
    run_dir: Path
    run_log_path: Path
    metadata_path: Path
    screenshots_dir: Path
    html_dir: Path

    def append_record(self, record: dict) -> None:
        with self.run_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")

    def write_metadata(self, metadata: dict) -> None:
        self.metadata_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2))

    def screenshot_path(self, label: Optional[str], index: int) -> Path:
        safe_label = _safe_filename(label or f"step_{index}")
        return self.screenshots_dir / f"{safe_label}.png"

    def html_snapshot_path(self, label: Optional[str], index: int) -> Path:
        safe_label = _safe_filename(label or f"step_{index}")
        return self.html_dir / f"{safe_label}.html"


def _safe_filename(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    cleaned = cleaned.strip("_")
    return cleaned or "artifact"


def init_run(runs_dir: Path, session_id: str) -> RunArtifacts:
    run_id = new_run_id()
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = run_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    html_dir = run_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)

    artifacts = RunArtifacts(
        run_id=run_id,
        run_dir=run_dir,
        run_log_path=run_dir / "run.jsonl",
        metadata_path=run_dir / "metadata.json",
        screenshots_dir=screenshots_dir,
        html_dir=html_dir,
    )

    metadata = {
        "run_id": run_id,
        "session_id": session_id,
        "started_at": _utc_now(),
        "finished_at": None,
        "status": "running",
    }
    artifacts.write_metadata(metadata)
    return artifacts


def finalize_run(artifacts: RunArtifacts, status: str) -> None:
    metadata = load_metadata(artifacts.run_dir)
    metadata["status"] = status
    metadata["finished_at"] = _utc_now()
    artifacts.write_metadata(metadata)


def load_metadata(run_dir: Path) -> dict:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def read_run_records(run_dir: Path) -> list[dict]:
    log_path = run_dir / "run.jsonl"
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def list_runs(runs_dir: Path) -> list[dict]:
    runs: list[dict] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        metadata = load_metadata(child)
        if not metadata:
            continue
        runs.append(metadata)

    def sort_key(item: dict) -> float:
        started = item.get("started_at")
        if not started:
            return 0.0
        try:
            return date_parser.parse(started).timestamp()
        except Exception:
            return 0.0

    runs.sort(key=sort_key, reverse=True)
    return runs


def load_run_detail(run_dir: Path) -> dict:
    metadata = load_metadata(run_dir)
    records = read_run_records(run_dir)
    steps = [r for r in records if r.get("type") == "step"]
    notes = [r for r in records if r.get("type") == "note"]
    manual_assist = None
    for record in steps:
        if record.get("status") == "needs_manual_assist":
            result = record.get("result") or {}
            manual_assist = {
                "message": result.get("reason") or result.get("message"),
                "screenshot": result.get("screenshot"),
                "timestamp": record.get("timestamp"),
            }
    return {
        "metadata": metadata,
        "records": records,
        "steps": steps,
        "notes": notes,
        "manual_assist": manual_assist,
    }
