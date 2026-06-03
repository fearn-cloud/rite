"""Read-only PBS restore-point fact loading for Backup Health."""

import datetime as dt
import json
from pathlib import Path

from .backup_health import RestorePointFact


def load_restore_point_facts_json(path):
    if not path:
        return ()
    raw = json.loads(Path(path).read_text())
    return tuple(
        RestorePointFact(
            vm_name=item["vm_name"],
            completed_at=dt.datetime.fromisoformat(item["completed_at"]),
            successful=item.get("successful", False),
        )
        for item in raw
    )
