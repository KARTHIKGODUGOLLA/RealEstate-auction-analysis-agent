"""Tiny persistent memory store for buyer profiles and saved auction analyses."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auction_agent.data import BUYER_PROFILE

DATA_DIR = Path(".data")
PROFILE_PATH = DATA_DIR / "buyer_profile.json"
ANALYSES_PATH = DATA_DIR / "auction_analyses.json"


def load_buyer_profile() -> dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    if not PROFILE_PATH.exists():
        save_buyer_profile(BUYER_PROFILE)
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def save_buyer_profile(profile: dict[str, Any]) -> dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return profile


def update_buyer_profile(updates: dict[str, Any]) -> dict[str, Any]:
    profile = load_buyer_profile()
    profile.update({key: value for key, value in updates.items() if value is not None})
    return save_buyer_profile(profile)


def save_analysis(analysis: Any) -> dict[str, Any]:
    DATA_DIR.mkdir(exist_ok=True)
    history = load_analysis_history()
    record = _serialize(analysis)
    record["saved_at"] = datetime.now(timezone.utc).isoformat()
    history.append(record)
    ANALYSES_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return record


def load_analysis_history() -> list[dict[str, Any]]:
    DATA_DIR.mkdir(exist_ok=True)
    if not ANALYSES_PATH.exists():
        ANALYSES_PATH.write_text("[]", encoding="utf-8")
    return json.loads(ANALYSES_PATH.read_text(encoding="utf-8"))


def _serialize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value
