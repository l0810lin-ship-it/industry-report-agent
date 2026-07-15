#!/usr/bin/env python3
"""Single-instance guard for direct pipeline-stage execution."""

from __future__ import annotations

import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path


def _active_pid(lock_dir: Path) -> int | None:
    try:
        pid = int((lock_dir / "pid").read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return pid
    return pid


@contextmanager
def pipeline_stage_lock(agent_dir: Path, stage: str):
    """Serialize direct stage calls while allowing the locked run.sh pipeline."""
    if os.environ.get("INDUSTRY_REPORT_PIPELINE_ACTIVE") == "1":
        yield
        return

    output_dir = agent_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    collect_lock = output_dir / ".collect.lock"
    collect_pid = _active_pid(collect_lock) if collect_lock.exists() else None
    if collect_pid:
        print(
            f"Pipeline busy: collect is active (PID {collect_pid}); wait instead of running {stage} directly.",
            file=sys.stderr,
        )
        raise SystemExit(75)

    lock_dir = output_dir / ".pipeline-stage.lock"
    try:
        lock_dir.mkdir()
    except FileExistsError:
        lock_pid = _active_pid(lock_dir)
        if lock_pid:
            active_stage = (
                (lock_dir / "stage").read_text(encoding="utf-8").strip()
                if (lock_dir / "stage").exists()
                else "unknown"
            )
            print(
                f"Pipeline busy: {active_stage} is active (PID {lock_pid}); wait instead of starting {stage}.",
                file=sys.stderr,
            )
            raise SystemExit(75)
        shutil.rmtree(lock_dir, ignore_errors=True)
        lock_dir.mkdir()

    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    (lock_dir / "stage").write_text(stage, encoding="utf-8")
    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)
