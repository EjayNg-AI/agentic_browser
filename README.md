# humanbrowse-cdp

Local FastAPI service for bounded, policy-guarded browsing via Chrome DevTools Protocol (CDP).
It connects to a dedicated Windows Chrome instance, executes a strict sequence of steps,
records artifacts to disk, and serves a local UI at `http://localhost:7500`.

## Scope and guardrails

- Local-only, single server on `127.0.0.1:7500`. No concurrency and no crawling features.
- No stealth or bot-evasion tactics. No automated CAPTCHA solving or paywall bypass.
- Manual Assist is required when blocked by CAPTCHA, login/MFA, bot interstitials,
  paywalls, or consent walls that block content.
- CLI output is restricted to a small JSON pointer; gathered content is only visible
  in the UI and in `runs/<run_id>/` artifacts.

## Architecture overview

- Windows Chrome is launched with `--remote-debugging-port` and a dedicated profile.
- The service connects via Playwright `connect_over_cdp()`.
- Each run writes `runs/<run_id>/metadata.json`, `run.jsonl`, and artifacts
  (screenshots and optional HTML snapshots).
- The UI is served by the same FastAPI app and fetches JSON from `/ui/api/*`.

## Endpoints (exact set)

- `GET /health`
- `POST /v1/run_steps`
- `POST /v1/resume`
- `POST /v1/close_session`
- `GET /v1/session_status?session_id=...`
- `GET /ui/api/runs`
- `GET /ui/api/runs/{run_id}`
- `GET /` (UI)
- `GET /runs/{run_id}` (UI run page)
- `GET /runs/{run_id}/*` (artifacts)

## Supported step types

- `goto(url, wait_until)`
- `click(selector|text|role)`
- `type(selector, text)`
- `press(key)`
- `wait_for(selector|text|load_state)`
- `scroll(pixels|to_selector)`
- `extract(selector?)`
- `extract_readable()`
- `links(scope="main")`
- `quote(query, context_chars=400)`
- `screenshot(label)`
- `pause_for_user(reason)`

## Execution

### 1) Start dedicated Windows Chrome
Run from Windows PowerShell (or from WSL invoking `powershell.exe`):

```powershell
./windows/Start-HumanChrome.ps1 -Port 9222 -UserDataDir "$env:LOCALAPPDATA\HumanBrowseProfile"
```

From WSL, you can invoke Windows PowerShell like this:

```bash
SCRIPT_WIN="$(wslpath -w "$(pwd)/windows/Start-HumanChrome.ps1")"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$SCRIPT_WIN" -Port 9222 -UserDataDir '$env:LOCALAPPDATA\HumanBrowseProfile'
```

Known-good example (explicit Chrome path):

```bash
SCRIPT_WIN="$(wslpath -w "$(pwd)/windows/Start-HumanChrome.ps1")"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$SCRIPT_WIN" -Port 9222 -ChromePath "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
```

You should see a check URL like `http://127.0.0.1:9222/json/version`.
If Chrome is not discovered automatically, pass `-ChromePath` explicitly.

### 2) Start the FastAPI server (WSL)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

# optional config
cp humanbrowse.yaml.example humanbrowse.yaml
export HUMANBROWSE_CONFIG=humanbrowse.yaml

uvicorn humanbrowse.service:app --host 127.0.0.1 --port 7500
```

### 3) Open the UI
Visit `http://localhost:7500` in your browser.

### 4) webctl examples
```bash
webctl health

webctl run --json '{"new_session": true, "steps": [{"type": "goto", "url": "https://example.com"}, {"type": "screenshot", "label": "home"}]}'

webctl run --file request.json
```

## Testing

```bash
pytest
```

The smoke test in `tests/test_smoke_optional.py` is skipped unless a CDP endpoint
is reachable at `http://127.0.0.1:9222/json/version`.

## Artifacts and UI

Each run is stored under `runs/<run_id>/` with:
- `metadata.json` for run status and timing
- `run.jsonl` for step results and note records
- `screenshots/` for requested screenshots
- `html/` for HTML snapshots when enabled

The UI lists runs on the home page and renders steps and notes on the run page.
Manual Assist runs show the blocking message and screenshot with a Resume button.
