import unittest
from datetime import datetime, timedelta, timezone

from unittest.mock import patch

from collector.collect import compute_gem_score, get_commit_count_recent


def repository(open_issues):
    now = datetime.now(timezone.utc)
    return {
        "created_at": (now - timedelta(days=400)).isoformat(),
        "pushed_at": (now - timedelta(days=1)).isoformat(),
        "stargazers_count": 200,
        "open_issues_count": open_issues,
        "description": "A documented production project with a detailed and useful description for adopters.",
        "topics": ["llm", "inference", "ai"],
        "license": {"spdx_id": "MIT"},
    }


class GemScoreTests(unittest.TestCase):
    @patch("collector.collect.gh_get")
    def test_commit_collection_identifies_automated_share(self, gh_get):
        commits = [
            {"author": {"login": "dependabot[bot]", "type": "Bot"}},
            {"author": {"login": "maintainer", "type": "User"}},
        ]
        gh_get.side_effect = [[commits[0]], commits]
        self.assertEqual(get_commit_count_recent("o", "r", include_automation=True),
                         (2, False, .5))

    def test_unresolved_issue_pressure_cannot_outrank_healthy_peer(self):
        healthy = compute_gem_score(repository(10), 30, 8, {
            "maintainer_responses_30d_lower_bound": 12,
            "issues_closed_30d_lower_bound": 12,
            "median_issue_response_hours": 12,
            "open_issue_growth_30d": -2,
            "top_contributor_share": .3,
        })
        pressured = compute_gem_score(repository(500), 30, 8, {
            "maintainer_responses_30d_lower_bound": 0,
            "issues_closed_30d_lower_bound": 0,
            "median_issue_response_hours": None,
            "open_issue_growth_30d": 40,
            "top_contributor_share": .3,
        })
        self.assertGreater(healthy, pressured)

    def test_score_emits_named_subscores_and_reasons(self):
        result = compute_gem_score(repository(5), 20, 6, {}, return_details=True)
        self.assertEqual(set(result["gem_subscores"]), {"activity", "quality", "visibility"})
        self.assertTrue(result["gem_reasons"])

    def test_automated_commit_volume_is_discounted(self):
        human = compute_gem_score(repository(5), 40, 5, {"automated_commit_share": 0})
        automated = compute_gem_score(repository(5), 40, 5, {"automated_commit_share": .9})
        self.assertGreater(human, automated)


if __name__ == "__main__":
    unittest.main()
