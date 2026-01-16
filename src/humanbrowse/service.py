import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .artifacts import init_run, list_runs, load_run_detail, finalize_run
from .browser_manager import BrowserManager, SessionManager
from .config import load_config
from .models import CloseSessionRequest, ResumeRequest, RunStepsRequest, RunStepsResponse
from .policy import DomainPolicy
from .steps import execute_steps

BASE_DIR = Path(__file__).resolve().parents[2]
UI_DIR = BASE_DIR / "ui"

settings = load_config(os.getenv("HUMANBROWSE_CONFIG"))
RUNS_DIR = (BASE_DIR / settings.runs_dir).resolve()
RUNS_DIR.mkdir(parents=True, exist_ok=True)

browser_manager = BrowserManager(settings)
session_manager = SessionManager(browser_manager)
domain_policy = DomainPolicy.from_config(
    settings.policy.mode, settings.policy.domains
)

app = FastAPI()

if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.post("/v1/run_steps", response_model=RunStepsResponse)
async def run_steps(payload: RunStepsRequest, request: Request) -> RunStepsResponse:
    session = await session_manager.get_or_create_session(
        payload.session_id, payload.new_session
    )
    if session.status == "paused" and not payload.new_session:
        base_url = str(request.base_url).rstrip("/")
        last = session.last_manual_assist or {}
        run_id = session.last_run_id or ""
        return RunStepsResponse(
            status="NEEDS_MANUAL_ASSIST",
            run_id=run_id,
            session_id=session.session_id,
            run_url=f"{base_url}/runs/{run_id}" if run_id else base_url,
            message=last.get("message", "Session paused. Resume required."),
            screenshot=last.get("screenshot"),
        )
    if settings.max_steps_per_run > 0 and len(payload.steps) > settings.max_steps_per_run:
        artifacts = init_run(RUNS_DIR, session.session_id)
        session.last_run_id = artifacts.run_id
        artifacts.append_record(
            {
                "type": "policy_violation",
                "kind": "max_steps_per_run",
                "message": "Maximum steps per run exceeded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        finalize_run(artifacts, "POLICY_VIOLATION")
        session.last_active = datetime.now(timezone.utc).isoformat()
        base_url = str(request.base_url).rstrip("/")
        return RunStepsResponse(
            status="POLICY_VIOLATION",
            run_id=artifacts.run_id,
            session_id=session.session_id,
            run_url=f"{base_url}/runs/{artifacts.run_id}",
            message="Maximum steps per run exceeded",
        )

    artifacts = init_run(RUNS_DIR, session.session_id)
    session.last_run_id = artifacts.run_id
    outcome = await execute_steps(
        session.page, payload.steps, artifacts, settings, policy=domain_policy
    )
    finalize_run(artifacts, outcome.status)
    if outcome.status == "NEEDS_MANUAL_ASSIST":
        session.status = "paused"
        session.last_manual_assist = {
            "message": outcome.message,
            "screenshot": outcome.screenshot,
            "run_id": artifacts.run_id,
        }
    session.last_active = datetime.now(timezone.utc).isoformat()
    base_url = str(request.base_url).rstrip("/")
    return RunStepsResponse(
        status=outcome.status,
        run_id=artifacts.run_id,
        session_id=session.session_id,
        run_url=f"{base_url}/runs/{artifacts.run_id}",
        message=outcome.message,
        screenshot=outcome.screenshot,
    )


@app.post("/v1/resume")
async def resume_session(payload: ResumeRequest) -> dict:
    ok = session_manager.resume_session(payload.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "ok", "session_id": payload.session_id}


@app.post("/v1/close_session")
async def close_session(payload: CloseSessionRequest) -> dict:
    ok = await session_manager.close_session(payload.session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "ok", "session_id": payload.session_id}


@app.get("/v1/session_status")
async def session_status(session_id: str) -> dict:
    status = session_manager.get_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="session not found")
    return status


@app.get("/ui/api/runs")
async def ui_runs() -> dict:
    return {"runs": list_runs(RUNS_DIR)}


@app.get("/ui/api/runs/{run_id}")
async def ui_run_detail(run_id: str) -> dict:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return load_run_detail(run_dir)


@app.get("/runs/{run_id}")
async def run_page(run_id: str) -> FileResponse:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run not found")
    return FileResponse(UI_DIR / "run.html")


@app.get("/runs/{run_id}/{artifact_path:path}")
async def run_artifact(run_id: str, artifact_path: str) -> FileResponse:
    run_dir = (RUNS_DIR / run_id).resolve()
    target = (run_dir / artifact_path).resolve()
    if not target.is_file() or run_dir not in target.parents:
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(target)
