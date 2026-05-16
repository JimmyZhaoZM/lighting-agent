"""
Run checkpoint utilities.

After each Phase completes, save its output to docs/checkpoints/ for traceability.
Keeps the 10 most recent files per phase; deletes older ones automatically.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_CHECKPOINT_DIR = Path(__file__).parents[2] / "docs" / "checkpoints"
_MAX_KEEP = 10


def save_phase1_checkpoint(rooms_data: list[dict]) -> Path:
    """Save Phase 1 output (list[Room] as dicts) to a timestamped checkpoint file.

    Keeps the _MAX_KEEP most recent files and deletes older ones.
    Returns the path of the saved file.
    """
    _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _CHECKPOINT_DIR / f"phase1_{timestamp}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rooms_data, f, ensure_ascii=False, indent=2)

    _prune(prefix="phase1_")
    return out_path


def _prune(prefix: str) -> None:
    """Delete oldest files with the given prefix, keeping only _MAX_KEEP."""
    files = sorted(_CHECKPOINT_DIR.glob(f"{prefix}*.json"))
    for old in files[:-_MAX_KEEP]:
        old.unlink(missing_ok=True)
