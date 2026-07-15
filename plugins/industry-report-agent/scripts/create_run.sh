#!/bin/bash
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE_DIR="$PLUGIN_DIR/scripts/project-template"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <target-dir>"
  exit 1
fi

TARGET_DIR="$1"

if [ -e "$TARGET_DIR" ]; then
  echo "Target already exists: $TARGET_DIR"
  exit 1
fi

mkdir -p "$(dirname "$TARGET_DIR")"
cp -R "$TEMPLATE_DIR" "$TARGET_DIR"
echo "$TARGET_DIR"
