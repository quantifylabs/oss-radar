"""Validate generated OSS Radar site assets before deployment."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
REQUIRED_META = [
    '<link rel="canonical"',
    'property="og:url"',
    'property="og:image"',
    'name="twitter:card"',
    'application/ld+json',
]
REQUIRED_REPO_FIELDS = {
    "name", "description", "stars", "forks", "language", "topics", "category",
    "url", "adoption_score", "adoption_label", "maintainer_health", "metrics_estimated",
}
CANONICAL_CATEGORIES = {
    "agent-framework", "model-serving", "fine-tuning", "rag-and-search",
    "dev-tools", "mcp", "evals-and-testing", "local-and-edge-ai",
    "gateways-and-routing", "ai-security-and-guardrails",
    "ai-coding-and-assistants", "ai-webui-and-interfaces",
    "multimodal-media", "vector-dbs-and-data",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    for rel in ["data.json", "robots.txt", "sitemap.xml", "index.html"]:
        if not (SITE / rel).exists():
            fail(f"missing site/{rel}")

    html = (SITE / "index.html").read_text()
    for needle in REQUIRED_META:
        if needle not in html:
            fail(f"missing homepage metadata: {needle}")

    data = json.loads((SITE / "data.json").read_text())
    datetime.fromisoformat(data["last_updated"])
    for key in ["stats", "trending", "gems", "abandoned", "discovery"]:
        if key not in data:
            fail(f"missing data key: {key}")
    if not data["trending"]:
        fail("trending list is empty")
    represented_categories = set()
    for section in ["discovery"]:
        for repo in data.get(section, []):
            missing = REQUIRED_REPO_FIELDS - set(repo)
            if missing:
                fail(f"{repo.get('name', '<unknown>')} missing fields: {sorted(missing)}")
            category = repo["category"]
            if category not in CANONICAL_CATEGORIES:
                fail(f"{repo.get('name', '<unknown>')} has unknown category: {category}")
            represented_categories.add(category)

    sitemap = (SITE / "sitemap.xml").read_text()
    for category in represented_categories:
        if not (SITE / "categories" / category / "index.html").is_file():
            fail(f"missing category page for {category}")
        if not (SITE / "feeds" / f"{category}.xml").is_file():
            fail(f"missing category feed for {category}")
        if f"/categories/{category}/" not in sitemap:
            fail(f"sitemap missing category URL for {category}")
    print("Site validation passed")


if __name__ == "__main__":
    main()
