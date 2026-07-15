#!/usr/bin/env python3
"""Shared hard gate for user-selected research mode and output formats."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VALID_SOURCES = {"user_selected", "user_delegated"}
MODE_PROFILES_FILE = Path(__file__).resolve().parent.parent / "mode_profiles.json"


def load_mode_profiles() -> dict:
    return json.loads(MODE_PROFILES_FILE.read_text(encoding="utf-8"))


def normalize_formats(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip().lower() for item in value if str(item).strip()))


def validate_intake_config(config: dict) -> tuple[str, list[str], list[dict]]:
    """Return normalized selections and failures; never apply silent defaults."""
    failures: list[dict] = []
    profiles = load_mode_profiles()
    valid_formats = set.intersection(*(
        set(profile.get("format_overhead_minutes", {})) for profile in profiles.values()
    ))
    mode = str(config.get("research_mode", "")).strip().lower()
    formats = normalize_formats(config.get("output", {}).get("formats", []))
    intake = config.get("intake", {})
    mode_selection = intake.get("mode_selection", {}) if isinstance(intake, dict) else {}
    format_selection = intake.get("format_selection", {}) if isinstance(intake, dict) else {}

    if mode not in profiles:
        failures.append({
            "check": "intake:research_mode",
            "detail": "请先让用户选择 Flash、Standard 或 Deep；不得静默使用默认模式",
        })
    if not formats or any(item not in valid_formats for item in formats):
        failures.append({
            "check": "intake:output_formats",
            "detail": "请先让用户选择 Markdown、Word 或 PowerPoint；格式可多选",
        })

    if mode_selection.get("status") != "selected":
        failures.append({"check": "intake:mode_selection_status", "detail": "mode_selection.status 必须是 selected"})
    if mode_selection.get("source") not in VALID_SOURCES:
        failures.append({
            "check": "intake:mode_selection_source",
            "detail": "source 必须记录为 user_selected 或 user_delegated",
        })
    if format_selection.get("status") != "selected":
        failures.append({"check": "intake:format_selection_status", "detail": "format_selection.status 必须是 selected"})
    if format_selection.get("source") not in VALID_SOURCES:
        failures.append({
            "check": "intake:format_selection_source",
            "detail": "source 必须记录为 user_selected 或 user_delegated",
        })
    return mode, formats, failures
