from pathlib import Path


ROOT = Path(__file__).parents[1]
HTML = (ROOT / "site" / "index.html").read_text()


def test_success_events_are_allowlisted_without_repo_payloads():
    for event in (
        "repository_opened", "feed_subscribed", "filters_applied",
        "comparison_created", "share_url_copied", "label_reported",
    ):
        assert event in HTML
    assert "JSON.stringify({event})" in HTML
    assert 'oss-radar-analytics-endpoint" content=""' in HTML


def test_feedback_and_share_controls_are_present():
    assert 'id="copy-share-url"' in HTML
    assert "recommendation-feedback.yml" in HTML
    for label in ("Incorrect category", "Misleading trend status", "Maintenance-risk dispute"):
        assert label in HTML


def test_privacy_and_evaluation_documentation_exists():
    assert (ROOT / "site" / "privacy.html").exists()
    assert (ROOT / "docs" / "analytics.md").exists()
    assert (ROOT / "docs" / "evaluation.md").exists()
    assert (ROOT / "tests" / "fixtures" / "scoring_benchmark.json").exists()
