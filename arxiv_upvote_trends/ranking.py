# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PATH = "./persistent_data/ranking_history.json"


def load_ranking_history(
    now: datetime,
    path: str = _DEFAULT_PATH,
    retention_days: int = 30,
) -> dict[str, datetime]:
    """Load ranking history, discarding entries older than retention_days."""
    file = Path(path)
    if not file.exists():
        return {}
    data = json.loads(file.read_text(encoding="utf-8"))
    cutoff = now - timedelta(days=retention_days)
    history = {}
    for arxiv_id, timestamp in data.items():
        first_seen = datetime.fromisoformat(timestamp)
        if first_seen >= cutoff:
            history[arxiv_id] = first_seen
    return history


def update_ranking_history(
    history: dict[str, datetime],
    arxiv_ids: list[str],
    now: datetime,
    path: str = _DEFAULT_PATH,
    retention_days: int = 30,
) -> None:
    """Merge new arxiv_ids into history and write to disk."""
    for arxiv_id in arxiv_ids:
        if arxiv_id not in history:
            history[arxiv_id] = now
    cutoff = now - timedelta(days=retention_days)
    data = {arxiv_id: first_seen.isoformat() for arxiv_id, first_seen in history.items() if first_seen >= cutoff}
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
