from datetime import datetime, timedelta, timezone

from collector.collect import compute_star_deltas, rank_trending


def test_weekly_growth_ranks_lower_star_repo_first():
    entries = [
        {"name": "famous/repo", "stars": 100_010, "stars_delta_7d": 10,
         "stars_delta_7d_valid": True, "days_since_push": 0, "archived": False},
        {"name": "small/fast", "stars": 1_100, "stars_delta_7d": 100,
         "stars_delta_7d_valid": True, "days_since_push": 2, "archived": False},
    ]

    assert [repo["name"] for repo in rank_trending(entries, 7)] == [
        "small/fast", "famous/repo"
    ]


def test_missing_history_is_invalid_not_zero_growth():
    now = datetime(2026, 8, 4, tzinfo=timezone.utc)
    history = {"snapshots": [{
        "timestamp": (now - timedelta(days=8)).isoformat(),
        "stars": {"known/repo": 90},
    }]}

    deltas = compute_star_deltas({"known/repo": 100, "new/repo": 20}, history, now)

    assert deltas["known/repo"]["delta_7d"] == 10
    assert deltas["known/repo"]["delta_7d_valid"] is True
    assert deltas["new/repo"]["delta_7d"] is None
    assert deltas["new/repo"]["delta_7d_valid"] is False
    assert deltas["new/repo"]["history_coverage_days"] == 0
