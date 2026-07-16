#!/usr/bin/env python3
"""Run frozen benchmark cases serially and preserve every attempt."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


FIELDS = [
    "sample_id", "system", "case_id", "scenario", "group", "status",
    "attempt_count", "started_at", "completed_at", "elapsed_seconds",
    "model", "search_backend", "run_dir", "input_path", "report_path",
    "metrics_path", "log_path", "input_sha256", "output_sha256", "warning",
    "error", "retry_count",
]


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--systems", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--retry-limit", type=int, default=1)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent
    cases_path = args.cases if args.cases.is_absolute() else base / args.cases
    systems_path = args.systems if args.systems.is_absolute() else base / args.systems
    root = args.root if args.root.is_absolute() else base / args.root
    root.mkdir(parents=True, exist_ok=True)
    (root / "prompts").mkdir(exist_ok=True)
    (root / "runs").mkdir(exist_ok=True)

    cases_document = load_json(cases_path)
    systems_document = load_json(systems_path)
    cases = cases_document.get("cases", cases_document) if isinstance(cases_document, dict) else cases_document
    systems = systems_document.get("systems", systems_document) if isinstance(systems_document, dict) else systems_document
    write_json(root / "cases.json", cases)
    write_json(root / "systems.json", systems)

    prompt_bytes = {}
    for case in cases:
        data = case["prompt"].encode("utf-8")
        prompt_path = root / "prompts" / f'{case["id"]}.txt'
        if prompt_path.exists() and prompt_path.read_bytes() != data:
            raise SystemExit(f"Frozen prompt changed: {prompt_path}")
        prompt_path.write_bytes(data)
        prompt_bytes[case["id"]] = data

    rows = []
    history = {}
    for system in systems:
        for case in cases:
            sample_id = f'{system["id"]}__{case["id"]}'
            sample_root = root / "runs" / sample_id
            sample_root.mkdir(parents=True, exist_ok=True)
            attempts = []
            final = None
            for attempt_no in range(1, args.retry_limit + 2):
                attempt_dir = sample_root / f"attempt-{attempt_no:02d}"
                attempt_dir.mkdir(exist_ok=False)
                input_path = attempt_dir / "input.txt"
                report_path = attempt_dir / "report.md"
                metrics_path = attempt_dir / "metrics.json"
                log_path = attempt_dir / "run.log"
                input_path.write_bytes(prompt_bytes[case["id"]])
                replacements = {"input": str(input_path), "output": str(attempt_dir), "sample_id": sample_id}
                command_template = system["command"]
                if isinstance(command_template, list):
                    command = [part.format(**replacements) for part in command_template]
                    command_display = shlex.join(command)
                else:
                    command_display = command_template.format(**replacements)
                    command = shlex.split(command_display)
                started = now()
                result = subprocess.run(
                    command, cwd=base, capture_output=True, text=True, check=False
                )
                completed = now()
                log_path.write_text(
                    f"command: {command_display}\nexit_code: {result.returncode}\n\n[stdout]\n"
                    f"{result.stdout}\n[stderr]\n{result.stderr}",
                    encoding="utf-8",
                )
                ok = result.returncode == 0 and report_path.exists() and report_path.stat().st_size > 0
                attempt = {
                    "attempt": attempt_no,
                    "status": "completed" if ok else "failed",
                    "started_at": iso(started),
                    "completed_at": iso(completed),
                    "elapsed_seconds": round((completed - started).total_seconds(), 3),
                    "exit_code": result.returncode,
                    "run_dir": relative(attempt_dir, root),
                    "error": "" if ok else "runner failed or report.md is missing/empty",
                }
                attempts.append(attempt)
                final = (attempt_dir, input_path, report_path, metrics_path, log_path, attempt)
                if ok:
                    break

            history[sample_id] = attempts
            attempt_dir, input_path, report_path, metrics_path, log_path, attempt = final
            output = report_path.read_bytes() if report_path.exists() else b""
            rows.append({
                "sample_id": sample_id,
                "system": system["id"],
                "case_id": case["id"],
                "scenario": case.get("scenario", ""),
                "group": case.get("group", ""),
                "status": attempt["status"],
                "attempt_count": len(attempts),
                "started_at": attempts[0]["started_at"],
                "completed_at": attempt["completed_at"],
                "elapsed_seconds": sum(item["elapsed_seconds"] for item in attempts),
                "model": system.get("model", "unknown"),
                "search_backend": system.get("search_backend", "unknown"),
                "run_dir": relative(attempt_dir, root),
                "input_path": relative(input_path, root),
                "report_path": relative(report_path, root) if report_path.exists() else "",
                "metrics_path": relative(metrics_path, root) if metrics_path.exists() else "",
                "log_path": relative(log_path, root),
                "input_sha256": sha256(input_path.read_bytes()),
                "output_sha256": sha256(output) if output else "",
                "warning": "",
                "error": attempt["error"],
                "retry_count": len(attempts) - 1,
            })

    with (root / "run_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    write_json(root / "attempt_history.json", history)
    completed_count = sum(row["status"] == "completed" for row in rows)
    failed_count = len(rows) - completed_count
    write_json(root / "state.json", {
        "status": "completed",
        "planned": len(rows),
        "completed": completed_count,
        "failed": failed_count,
        "serial_execution": True,
        "updated_at": iso(now()),
    })
    print(json.dumps({"planned": len(rows), "completed": completed_count, "failed": failed_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
