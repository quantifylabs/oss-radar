import unittest

from collector.render_pages import repositories_by_category


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


if __name__ == "__main__":
    unittest.main()
