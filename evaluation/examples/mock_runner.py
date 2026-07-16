#!/usr/bin/env python3
"""Deterministic fake runner for harness smoke tests only."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--label", required=True)
args = parser.parse_args()

prompt = Path(args.input).read_text(encoding="utf-8")
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
(out / "report.md").write_text(
    "# Mock research report\n\n## Decision\nRecommendation is provisional.\n\n"
    f"## Input coverage\n{prompt}\n\n## Evidence limits\nNo external evidence was collected. "
    "All five claims are intentionally unverifiable in this smoke test.\n\n"
    "## 90-day action\nRun a measured pilot; stop if evidence remains unavailable.\n",
    encoding="utf-8",
)
(out / "metrics.json").write_text(json.dumps({"status": "completed", "mock": True}, indent=2), encoding="utf-8")
