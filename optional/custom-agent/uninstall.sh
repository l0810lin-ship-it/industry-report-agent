#!/bin/bash
set -euo pipefail

TARGET="${CODEX_HOME:-$HOME/.codex}/agents/industry_report.toml"
if [ ! -f "$TARGET" ]; then
  echo "industry_report is not installed."
  exit 0
fi

rm "$TARGET"
echo "Removed industry_report custom Agent: $TARGET"
