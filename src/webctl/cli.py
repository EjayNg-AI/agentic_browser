import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx


def _print_json(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.stdout.write("\n")


def health(base_url: str) -> int:
    try:
        resp = httpx.get(f"{base_url}/health", timeout=5)
        resp.raise_for_status()
        _print_json(resp.json())
        return 0
    except Exception as exc:
        _print_json({"status": "error", "error": str(exc)})
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="webctl")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:7500",
        help="Base URL for the humanbrowse service",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("health", help="Check service health")
    run_parser = subparsers.add_parser("run", help="Run a step sequence")
    run_parser.add_argument("--file", help="Path to JSON request body")
    run_parser.add_argument("--json", help="Inline JSON request body")

    args = parser.parse_args()

    if args.command == "health":
        raise SystemExit(health(args.base_url))
    if args.command == "run":
        if not args.file and not args.json:
            _print_json({"status": "error", "error": "Provide --file or --json"})
            raise SystemExit(1)
        try:
            if args.file:
                payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
            else:
                payload = json.loads(args.json)
        except Exception as exc:
            _print_json({"status": "error", "error": f"Invalid JSON: {exc}"})
            raise SystemExit(1)
        try:
            resp = httpx.post(
                f"{args.base_url}/v1/run_steps", json=payload, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
            _print_json(
                {
                    "status": data.get("status"),
                    "run_id": data.get("run_id"),
                    "session_id": data.get("session_id"),
                    "run_url": data.get("run_url"),
                }
            )
            raise SystemExit(0)
        except Exception as exc:
            _print_json({"status": "error", "error": str(exc)})
            raise SystemExit(1)


if __name__ == "__main__":
    main()
