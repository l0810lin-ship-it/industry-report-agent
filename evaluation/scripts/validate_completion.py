#!/usr/bin/env python3
"""Fail closed unless all benchmark artifacts are internally consistent."""
import argparse, csv, hashlib, json
from collections import Counter
from pathlib import Path

REQUIRED = ["cases.json", "systems.json", "run_manifest.csv", "hard_metrics.csv", "claim_audit.csv", "blind_scores.csv", "comparison_report.md", "resume_metrics.md", "state.json", "attempt_history.json"]
def sha(data): return hashlib.sha256(data).hexdigest()
def read_csv(path): return list(csv.DictReader(path.open(encoding="utf-8")))

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", required=True, type=Path); args = parser.parse_args(); root = args.root.resolve()
    errors = [f"missing {name}" for name in REQUIRED if not (root / name).exists()]
    if errors: print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2)); return 1
    cases = json.loads((root / "cases.json").read_text(encoding="utf-8")); systems = json.loads((root / "systems.json").read_text(encoding="utf-8")); state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    if isinstance(cases, dict): cases = cases.get("cases", [])
    if isinstance(systems, dict): systems = systems.get("systems", [])
    manifest = read_csv(root / "run_manifest.csv"); metrics = read_csv(root / "hard_metrics.csv"); claims = read_csv(root / "claim_audit.csv"); scores = read_csv(root / "blind_scores.csv"); expected = len(cases) * len(systems); case_map = {case["id"]: case["prompt"].encode("utf-8") for case in cases}
    if len(manifest) != expected: errors.append(f"manifest has {len(manifest)} rows; expected {expected}")
    if len(metrics) != expected: errors.append(f"hard metrics has {len(metrics)} rows; expected {expected}")
    completed = 0
    for row in manifest:
        if row["status"] not in {"completed", "failed"}: errors.append(f'{row["sample_id"]}: non-terminal status')
        input_path = root / row["input_path"]
        if not input_path.exists() or input_path.read_bytes() != case_map.get(row["case_id"], b"__missing__"): errors.append(f'{row["sample_id"]}: frozen input mismatch')
        elif sha(input_path.read_bytes()) != row["input_sha256"]: errors.append(f'{row["sample_id"]}: input hash mismatch')
        if row["status"] == "completed":
            completed += 1; report = root / row["report_path"]
            if not report.exists() or report.stat().st_size == 0: errors.append(f'{row["sample_id"]}: report missing or empty')
            elif sha(report.read_bytes()) != row["output_sha256"]: errors.append(f'{row["sample_id"]}: output hash mismatch')
    claim_counts = Counter(row["sample_id"] for row in claims)
    for row in manifest:
        wanted = 5 if row["status"] == "completed" else 0
        if claim_counts[row["sample_id"]] != wanted: errors.append(f'{row["sample_id"]}: expected {wanted} claims, got {claim_counts[row["sample_id"]]}')
    pending = sum(row["verification_status"] == "pending" for row in claims)
    if pending: errors.append(f"{pending} claim audits remain pending")
    if len(scores) != completed or len({row["blind_id"] for row in scores}) != completed: errors.append("blind scores are incomplete or duplicated")
    if state.get("status") != "completed" or state.get("planned") != expected or state.get("completed") != completed: errors.append("state.json does not match terminal manifest counts")
    for name in ("comparison_report.md", "resume_metrics.md"):
        if not (root / name).read_text(encoding="utf-8").strip(): errors.append(f"{name} is empty")
    result = {"valid": not errors, "planned": expected, "completed": completed, "errors": errors}; print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if not errors else 1

if __name__ == "__main__": raise SystemExit(main())
