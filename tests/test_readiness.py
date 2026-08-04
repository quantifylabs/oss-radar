import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from collector.collect import (
    build_trend_reasons,
    compute_adoption_readiness,
    get_commit_count_recent,
    get_contributor_metrics,
)


def repository(**overrides):
    now = datetime.now(timezone.utc)
    repo = {
        "pushed_at": now.isoformat(), "stargazers_count": 100,
        "forks_count": 20, "open_issues_count": 5, "topics": ["llm"] * 5,
        "license": {"spdx_id": "MIT"}, "archived": False,
    }
    repo.update(overrides)
    return repo


def signals(**overrides):
    values = {
        "commits_30d_lower_bound": 20, "contributors_total_lower_bound": 8,
        "latest_release_age_days": 20, "issue_responses_30d_lower_bound": 5,
        "pull_request_responses_30d_lower_bound": 3,
        "top_contributor_share": .3,
    }
    values.update(overrides)
    return values


class MetricCollectionTests(unittest.TestCase):
    @patch("collector.collect.gh_get")
    def test_capped_metrics_are_lower_bounds(self, gh_get):
        gh_get.side_effect = [[{"sha": "one"}], [{"sha": str(i)} for i in range(100)]]
        self.assertEqual(get_commit_count_recent("o", "r"), (100, True))

        gh_get.side_effect = [[{"contributions": 1} for _ in range(100)]]
        result = get_contributor_metrics("o", "r")
        self.assertEqual(result["contributors_total_lower_bound"], 100)
        self.assertTrue(result["contributors_capped"])

    @patch("collector.collect.gh_get", return_value=None)
    def test_missing_api_responses_remain_missing(self, _gh_get):
        self.assertEqual(get_commit_count_recent("o", "r"), (None, False))
        self.assertIsNone(get_contributor_metrics("o", "r")["contributors_total_lower_bound"])


class ReadinessTests(unittest.TestCase):
    def test_archived_repository_is_high_risk(self):
        result = compute_adoption_readiness(repository(archived=True), signals())
        self.assertEqual(result["adoption_score"], 0)
        self.assertEqual(result["adoption_label"], "high risk")
        self.assertIn("repository is archived", result["risk_signals"])

    def test_stale_release_is_explained_as_risk(self):
        result = compute_adoption_readiness(repository(), signals(latest_release_age_days=500))
        self.assertTrue(any("500 days old" in risk for risk in result["risk_signals"]))

    def test_concentrated_maintenance_is_explained_as_risk(self):
        result = compute_adoption_readiness(repository(), signals(top_contributor_share=.9))
        self.assertTrue(any("concentrated" in risk for risk in result["risk_signals"]))

    def test_missing_is_not_scored_as_zero(self):
        missing = compute_adoption_readiness(repository(), signals(
            commits_30d_lower_bound=None, contributors_total_lower_bound=None,
            latest_release_age_days=None, issue_responses_30d_lower_bound=None,
            pull_request_responses_30d_lower_bound=None,
            top_contributor_share=None))
        self.assertEqual(missing["data_confidence"], "low")
        self.assertIn("commit_activity", missing["missing_inputs"])

    def test_lifetime_contributors_are_not_called_active(self):
        reasons = build_trend_reasons({"category": "dev-tools",
            "contributors_total_lower_bound": 10})
        self.assertIn("lifetime contributors", reasons[0])
        self.assertNotIn("active contributors", reasons[0])


if __name__ == "__main__":
    unittest.main()
