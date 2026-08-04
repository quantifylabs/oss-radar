import json
import unittest
from unittest.mock import patch

from collector.render_pages import load_data, repositories_by_category


class RepositoriesByCategoryTests(unittest.TestCase):
    def test_deduplicates_repositories_across_sections(self):
        first = {"name": "owner/shared", "category": "model-serving", "stars": 100}
        duplicate = {"name": "owner/shared", "category": "model-serving", "stars": 100}
        unique = {"name": "owner/unique", "category": "model-serving", "stars": 20}

        categories = repositories_by_category({
            "trending": [first],
            "gems": [unique],
            "abandoned": [duplicate],
        })

        self.assertEqual(categories["model-serving"], [first, unique])

    def test_preserves_first_section_and_repository_order(self):
        categories = repositories_by_category({
            "trending": [
                {"name": "owner/first", "category": "dev-tools"},
                {"name": "owner/second", "category": "dev-tools"},
            ],
            "gems": [{"name": "owner/first", "category": "dev-tools"}],
            "abandoned": [{"name": "owner/third", "category": "dev-tools"}],
        })

        self.assertEqual(
            [repo["name"] for repo in categories["dev-tools"]],
            ["owner/first", "owner/second", "owner/third"],
        )

    def test_prefers_complete_discovery_index(self):
        discovery = [
            {"name": "owner/indexed", "category": "mcp"},
            {"name": "owner/also-indexed", "category": "dev-tools"},
        ]
        categories = repositories_by_category({
            "discovery": discovery,
            "trending": [{"name": "owner/limited", "category": "mcp"}],
        })

        self.assertEqual(categories, {
            "mcp": [discovery[0]],
            "dev-tools": [discovery[1]],
        })

    def test_load_data_expands_discovery_pages(self):
        manifest = {"discovery_pages": [{"url": "data/discovery/1.json"}]}
        with patch("collector.render_pages.DATA_FILE") as data_file, patch(
            "collector.render_pages.SITE"
        ) as site:
            data_file.read_text.return_value = json.dumps(manifest)
            site.__truediv__.return_value.read_text.return_value = json.dumps([
                {"name": "owner/chunked", "category": "mcp"}
            ])
            self.assertEqual(load_data()["discovery"][0]["name"], "owner/chunked")


if __name__ == "__main__":
    unittest.main()
