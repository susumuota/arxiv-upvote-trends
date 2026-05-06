# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from datetime import UTC, datetime, timedelta

from arxiv_upvote_trends.ranking import load_ranking_history, update_ranking_history


def test_load_returns_empty_dict_when_file_missing(tmp_path):
    result = load_ranking_history(datetime.now(UTC), path=str(tmp_path / "missing.json"))
    assert result == {}


def test_save_and_load_round_trip(tmp_path):
    path = str(tmp_path / "history.json")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    update_ranking_history({}, ["2604.00001", "2604.00002"], now, path=path)
    result = load_ranking_history(now, path=path)

    assert result == {"2604.00001": now, "2604.00002": now}


def test_load_excludes_entries_older_than_retention(tmp_path):
    path = str(tmp_path / "history.json")
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    old = now - timedelta(days=31)

    update_ranking_history({}, ["2604.00001"], old, path=path)
    update_ranking_history(
        load_ranking_history(old, path=path),
        ["2604.00002"],
        now,
        path=path,
    )

    result = load_ranking_history(now, path=path)
    assert "2604.00001" not in result
    assert "2604.00002" in result


def test_update_preserves_existing_first_seen(tmp_path):
    path = str(tmp_path / "history.json")
    first_seen = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    update_ranking_history({}, ["2604.00001"], first_seen, path=path)
    history = load_ranking_history(now, path=path)
    update_ranking_history(history, ["2604.00001", "2604.00002"], now, path=path)

    result = load_ranking_history(now, path=path)
    assert result["2604.00001"] == first_seen
    assert result["2604.00002"] == now


def test_update_excludes_expired_entries(tmp_path):
    path = str(tmp_path / "history.json")
    old = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)

    update_ranking_history({}, ["2604.00001"], old, path=path)
    history = load_ranking_history(now, path=path)
    update_ranking_history(history, ["2604.00002"], now, path=path)

    result = load_ranking_history(now, path=path)
    assert "2604.00001" not in result
    assert "2604.00002" in result
