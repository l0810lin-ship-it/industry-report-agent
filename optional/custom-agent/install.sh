#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/industry_report.toml"
TARGET_DIR="${CODEX_HOME:-$HOME/.codex}/agents"
TARGET="$TARGET_DIR/industry_report.toml"

if [ ! -f "$SOURCE" ]; then
  echo "Missing custom Agent definition: $SOURCE" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
if [ -f "$TARGET" ] && cmp -s "$SOURCE" "$TARGET"; then
  echo "industry_report is already installed: $TARGET"
  exit 0
fi

if [ -f "$TARGET" ]; then
  BACKUP="$TARGET.backup.$(date +%Y%m%d%H%M%S)"
  cp "$TARGET" "$BACKUP"
  echo "Existing definition backed up to: $BACKUP"
fi

install -m 600 "$SOURCE" "$TARGET"
echo "Installed industry_report custom Agent: $TARGET"
echo "Start a new Codex task to load it."
