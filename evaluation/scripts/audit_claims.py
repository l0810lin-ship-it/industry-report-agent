#!/usr/bin/env python3
"""Extract five decision-changing claims for human verification."""

import argparse
import csv
import re
from pathlib import Path
from urllib.parse import urlparse


FIELDS = ["sample_id", "claim_id", "claim_text", "numeric_claim", "cited_url",
          "source_domain", "is_primary", "source_access_status", "verification_status",
          "verification_note"]


def candidates(text: str):
    lines = [re.sub(r"^[#>*\-\d.\s]+", "", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if len(line) >= 18 and not re.fullmatch(r"[|:\-\s]+", line)]
    lines.sort(key=lambda line: (not bool(re.search(r"\d|建议|应当|进入|风险|recommend|market", line, re.I)), -len(line)))
    unique = []
    for line in lines:
        if line not in unique:
            unique.append(line[:800])
    return unique[:5]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--demo-label-unverifiable", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = list(csv.DictReader((root / "run_manifest.csv").open(encoding="utf-8")))
    rows = []
    for item in manifest:
        if item["status"] != "completed":
            continue
        text = (root / item["report_path"]).read_text(encoding="utf-8")
        claims = candidates(text)
        while len(claims) < 5:
            claims.append(f"No additional decision-changing claim extracted ({len(claims) + 1})")
        for index, claim in enumerate(claims, 1):
            match = re.search(r"https?://[^\s)>]+", claim)
            url = match.group(0).rstrip(".,;:") if match else ""
            rows.append({
                "sample_id": item["sample_id"], "claim_id": f"C{index}", "claim_text": claim,
                "numeric_claim": bool(re.search(r"\d", claim)), "cited_url": url,
                "source_domain": urlparse(url).netloc.lower() if url else "",
                "is_primary": "unknown", "source_access_status": "not_checked",
                "verification_status": "unverifiable" if args.demo_label_unverifiable else "pending",
                "verification_note": "mock smoke test only; no external evidence" if args.demo_label_unverifiable else "human review required",
            })
    with (root / "claim_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} claim rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
