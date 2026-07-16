#!/usr/bin/env python3
"""Create anonymous report packets and apply a transparent smoke-test rubric."""
import argparse, csv, hashlib, json, re, shutil
from pathlib import Path

FIELDS = ["blind_id", "scenario", "group", "rubric", "total_score", "judge_method", "judge_note"]

def score(text):
    headings = len(re.findall(r"(?m)^#{1,6}\s+", text)); numbers = len(re.findall(r"\d", text)); urls = len(re.findall(r"https?://", text))
    flags = sum(bool(re.search(pattern, text, re.I)) for pattern in [r"限制|不确定|待验证|limitation|uncertain", r"90\s*天|行动|试点|action|pilot", r"竞争|竞品|competition|competitor", r"市场|规模|TAM|market"])
    return min(100.0, round(min(headings, 6) * 5 + min(numbers, 10) * 2 + min(urls, 5) * 3 + flags * 10, 2))

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", required=True, type=Path); args = parser.parse_args()
    root = args.root.resolve(); packet_dir = root / "blind" / "packets"; packet_dir.mkdir(parents=True, exist_ok=True)
    manifest = list(csv.DictReader((root / "run_manifest.csv").open(encoding="utf-8"))); mapping = {}; rows = []
    for item in manifest:
        if item["status"] != "completed": continue
        blind_id = "B-" + hashlib.sha256(item["sample_id"].encode()).hexdigest()[:10].upper()
        target = packet_dir / f"{blind_id}.md"; shutil.copyfile(root / item["report_path"], target); mapping[blind_id] = item["sample_id"]
        rows.append({"blind_id": blind_id, "scenario": item["scenario"], "group": item["group"], "rubric": "public_smoke_rubric_v1", "total_score": score(target.read_text(encoding="utf-8")), "judge_method": "anonymous_deterministic_heuristic", "judge_note": "Harness smoke score only; use independent blind judges for publishable quality claims"})
    (root / "blind" / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (root / "blind_scores.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} anonymous scores"); return 0

if __name__ == "__main__": raise SystemExit(main())
