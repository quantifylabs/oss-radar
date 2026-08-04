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


def test_fetch_failure_offers_recovery_without_exposing_collector_commands():
    assert "if(!response.ok)throw Error(`HTTP ${response.status}`)" in HTML
    assert "if(!validateData(payload))throw Error('Invalid radar data')" in HTML
    assert 'id="retry-fetch"' in HTML
    assert 'href="/trending/"' in HTML
    assert "oss-radar-last-update" in HTML
    assert "collector/collect.py" not in HTML


def test_partial_data_uses_safe_formatters_and_unavailable_copy():
    for helper in ("safeNumber", "safeDate", "safeArray", "safeLabel", "safeScore"):
        assert f"function {helper}" in HTML
    assert "const UNAVAILABLE = 'Unavailable'" in HTML
    assert "every(key=>Array.isArray(value[key])&&value[key].every(isRecord))" in HTML


def test_tabs_expose_selection_panel_relationship_and_keyboard_navigation():
    assert "aria-selected=" in HTML
    assert 'aria-controls="repo-list"' in HTML
    assert 'role="tabpanel"' in HTML
    assert "ArrowRight" in HTML and "ArrowLeft" in HTML
    assert "event.key==='Home'" in HTML and "event.key==='End'" in HTML
    assert ":focus-visible" in HTML
    assert 'aria-pressed="${state.window===w}"' in HTML


def test_timestamp_is_explicitly_rendered_in_utc():
    assert "timeZone:'UTC'" in HTML
    assert "timeZoneName:'short'" in HTML


def test_cards_have_a_named_github_action_instead_of_a_linked_container():
    assert '<article class="repo">' in HTML
    assert 'class="github-action"' in HTML
    assert 'aria-label="Open ${escapeHtml(name)} on GitHub"' in HTML
