import unittest

from collector.collect import CATEGORY_MAP, assign_category


class AssignCategoryTests(unittest.TestCase):
    REVIEWED_REPOSITORIES = [
        ("n8n-io/n8n", "Workflow automation platform with MCP support", ["workflow-automation", "mcp"], "dev-tools"),
        ("modelcontextprotocol/servers", "Reference MCP server implementations", ["mcp-server"], "mcp"),
        ("continuedev/continue", "Open-source AI coding assistant", ["code-assistant", "mcp"], "ai-coding-and-assistants"),
        ("BerriAI/litellm", "LLM gateway and proxy with MCP integration", ["litellm", "mcp"], "gateways-and-routing"),
        ("open-webui/open-webui", "An extensible LLM web UI", ["webui", "mcp"], "ai-webui-and-interfaces"),
        ("modelcontextprotocol/docs", "Documentation repository for the Model Context Protocol", ["mcp"], "dev-tools"),
    ]

    def test_reviewed_repository_fixtures_include_explainable_confidence(self):
        for name, description, topics, expected in self.REVIEWED_REPOSITORIES:
            with self.subTest(name=name):
                result = assign_category(topics, name, description, return_details=True)
                self.assertEqual(result["category"], expected)
                self.assertGreaterEqual(result["category_confidence"], .5)
                self.assertTrue(result["category_reasons"])

    def test_cross_category_project_retains_secondary_category(self):
        result = assign_category(["code-assistant", "llm-evaluation"],
                                 "example/copilot-evals", "Coding assistant with LLM evaluation",
                                 return_details=True)
        self.assertEqual(result["category"], "evals-and-testing")
        self.assertIn("ai-coding-and-assistants", result["secondary_categories"])
        self.assertIn("topic:llm-evaluation", result["category_reasons"])

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
