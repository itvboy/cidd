"""Explicit validated snapshot selection for CIDD projects."""

from __future__ import annotations

import json
from pathlib import Path

from cidd.engine.snapshot import SnapshotError, verify


def select_active_snapshot(project_root: Path) -> Path | None:
    state_file = project_root / ".cidd" / "active-snapshot.json"

    if not state_file.is_file():
        return None

    try:
        state = json.loads(state_file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SnapshotError(
            f"Cannot read active snapshot state: {exc}"
        ) from exc

    if state.get("schema") != "cidd.active-snapshot/0.1":
        raise SnapshotError("Unsupported active snapshot schema")

    name = state.get("snapshot")

    if (
        not isinstance(name, str)
        or not name
        or name in (".", "..")
        or not name.replace("-", "").replace("_", "").isalnum()
    ):
        raise SnapshotError("Invalid active snapshot identifier")

    snapshot_dir = project_root / ".cidd" / "snapshots" / name

    if not snapshot_dir.is_dir():
        raise SnapshotError(
            f"Active snapshot not found: {snapshot_dir}"
        )

    verify(snapshot_dir)
    return snapshot_dir