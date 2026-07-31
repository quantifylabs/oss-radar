import unittest

from collector.collect import CATEGORY_MAP, assign_category


class AssignCategoryTests(unittest.TestCase):
    def test_representative_topic_for_every_category(self):
        examples = {
            "agent-framework": "crewai",
            "model-serving": "vllm",
            "fine-tuning": "qlora",
            "rag-and-search": "semantic-search",
            "dev-tools": "prompt-engineering",
            "mcp": "model-context-protocol",
            "evals-and-testing": "llm-testing",
            "local-and-edge-ai": "llama-cpp",
            "gateways-and-routing": "llm-router",
            "ai-security-and-guardrails": "prompt-injection",
            "ai-coding-and-assistants": "code-assistant",
            "ai-webui-and-interfaces": "chat-ui",
            "multimodal-media": "text-to-video",
            "vector-dbs-and-data": "vector-database",
        }
        self.assertEqual(set(examples), set(CATEGORY_MAP))
        for category, topic in examples.items():
            with self.subTest(category=category):
                self.assertEqual(assign_category([topic]), category)

    def test_specific_signal_wins_tie_with_generic_signal(self):
        cases = {
            "code-assistant": "ai-coding-and-assistants",
            "prompt-injection": "ai-security-and-guardrails",
            "llm-gateway": "gateways-and-routing",
            "vector-database": "vector-dbs-and-data",
            "chat-ui": "ai-webui-and-interfaces",
        }
        for specific, category in cases.items():
            self.assertEqual(assign_category(["llm", "ai-tools", "langchain", specific]), category)

    def test_topics_are_case_insensitive(self):
        self.assertEqual(assign_category(["CoDe-AsSiStAnT"]), "ai-coding-and-assistants")

    def test_no_match_falls_back_to_dev_tools(self):
        self.assertEqual(assign_category(["unrelated-topic"]), "dev-tools")
        self.assertEqual(assign_category([]), "dev-tools")

    def test_legacy_safety_topics_migrate(self):
        self.assertEqual(assign_category(["ai-safety", "guardrails"]), "ai-security-and-guardrails")
        self.assertEqual(assign_category(["ai-evaluation"]), "evals-and-testing")

    def test_legacy_mlops_topics_migrate(self):
        self.assertEqual(assign_category(["mlops", "model-serving"]), "model-serving")
        self.assertEqual(assign_category(["mlops", "feature-store"]), "vector-dbs-and-data")
        self.assertEqual(assign_category(["mlops"]), "model-serving")


if __name__ == "__main__":
    unittest.main()
