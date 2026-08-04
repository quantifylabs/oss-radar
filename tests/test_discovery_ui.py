from pathlib import Path


HTML = (Path(__file__).parents[1] / "site" / "index.html").read_text()


def test_discovery_controls_remain_available_and_labelled():
    for control_id in (
        "search", "sort", "category", "language", "license", "health",
        "adoption", "stars-min", "stars-max", "quality", "result-count",
    ):
        assert f'id="{control_id}"' in HTML
    assert 'aria-label="Repository views"' in HTML
    assert 'aria-live="polite"' in HTML


def test_shareable_state_and_comparison_hooks_remain_available():
    for hook in (
        "readUrlState", "writeUrlState", "popstate", "URLSearchParams",
        "toggleCompare", 'id="compare-panel"', 'aria-pressed=',
    ):
        assert hook in HTML


def test_every_requested_sort_is_exposed():
    for value in (
        "growth", "relative", "gem", "adoption", "risk", "commits",
        "stars", "newest",
    ):
        assert f'<option value="{value}">' in HTML
