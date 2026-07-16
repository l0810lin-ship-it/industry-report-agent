#!/usr/bin/env python3
"""Build deterministic, model-independent report metrics."""

import argparse
import csv
import re
from pathlib import Path
from urllib.parse import urlparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = list(csv.DictReader((root / "run_manifest.csv").open(encoding="utf-8")))
    rows = []
    for item in manifest:
        text = ""
        if item["status"] == "completed":
            text = (root / item["report_path"]).read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s)>]+", text)
        domains = {urlparse(url.rstrip(".,;:")).netloc.lower() for url in urls}
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        latin = len(re.findall(r"\b[A-Za-z]+\b", text))
        rows.append({
            "sample_id": item["sample_id"], "system": item["system"],
            "case_id": item["case_id"], "scenario": item["scenario"],
            "group": item["group"], "status": item["status"],
            "elapsed_seconds": item["elapsed_seconds"], "model": item["model"],
            "search_backend": item["search_backend"], "bytes": len(text.encode("utf-8")),
            "nonspace_chars": len(re.sub(r"\s", "", text)), "chinese_chars": chinese,
            "latin_words": latin, "dominant_language": "zh" if chinese >= latin else "en",
            "heading_count": len(re.findall(r"(?m)^#{1,6}\s+", text)),
            "table_row_count": len(re.findall(r"(?m)^\|.*\|\s*$", text)),
            "numeric_expression_count": len(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?:%|万|亿|元|美元)?", text)),
            "url_count": len(urls), "independent_domain_count": len(domains),
            "source_section_present": bool(re.search(r"(?im)^#{1,6}\s*(来源|参考|sources?|references?)", text)),
        })
    fields = list(rows[0]) if rows else ["sample_id"]
    with (root / "hard_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} metric rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
