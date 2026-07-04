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
    for key in ["stats", "trending", "gems", "abandoned"]:
        if key not in data:
            fail(f"missing data key: {key}")
    if not data["trending"]:
        fail("trending list is empty")
    for section in ["trending", "gems", "abandoned"]:
        for repo in data.get(section, []):
            missing = REQUIRED_REPO_FIELDS - set(repo)
            if missing:
                fail(f"{repo.get('name', '<unknown>')} missing fields: {sorted(missing)}")
    print("Site validation passed")


if __name__ == "__main__":
    main()
