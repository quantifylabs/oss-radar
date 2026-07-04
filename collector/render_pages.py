"""Generate crawlable static pages for OSS Radar."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA_FILE = SITE / "data.json"
BASE_URL = "https://radar.aegismemory.com"


def load_data() -> dict:
    return json.loads(DATA_FILE.read_text())


def h(value) -> str:
    return html.escape(str(value or ""), quote=True)


def repo_items(repos: list[dict]) -> str:
    if not repos:
        return "<p>No repositories found for this view yet.</p>"
    items = []
    for repo in repos:
        topics = " ".join(f"<span>{h(t)}</span>" for t in repo.get("topics", [])[:6])
        reasons = "; ".join(repo.get("trend_reasons", [])[:2])
        items.append(
            f"""
            <article class="repo-card">
              <h2><a href="{h(repo.get('url'))}">{h(repo.get('name'))}</a></h2>
              <p>{h(repo.get('description') or 'No description')}</p>
              <dl>
                <dt>Category</dt><dd>{h(str(repo.get('category', '')).replace('-', ' '))}</dd>
                <dt>Stars</dt><dd>{int(repo.get('stars', 0)):,}</dd>
                <dt>Adoption</dt><dd>{h(repo.get('adoption_label', 'watch'))} ({float(repo.get('adoption_score', 0)) * 100:.0f}%)</dd>
                <dt>Maintainer health</dt><dd>{h(repo.get('maintainer_health', 'watch'))}</dd>
              </dl>
              {f'<p><strong>Why:</strong> {h(reasons)}</p>' if reasons else ''}
              {f'<p class="topics">{topics}</p>' if topics else ''}
            </article>
            """
        )
    return "\n".join(items)


def page(title: str, description: str, path: str, repos: list[dict]) -> str:
    canonical = f"{BASE_URL}{path}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{h(title)}</title>
<meta name="description" content="{h(description)}">
<link rel="canonical" href="{h(canonical)}">
<style>
body {{ font-family: system-ui, sans-serif; margin: 0; background: #0b0b10; color: #e2e2ef; line-height: 1.6; }}
main {{ max-width: 920px; margin: 0 auto; padding: 32px 16px 64px; }}
a {{ color: #8b8df8; }}
.repo-card {{ border: 1px solid #252535; border-radius: 12px; padding: 16px; margin: 12px 0; background: #13131b; }}
dl {{ display: grid; grid-template-columns: 150px 1fr; gap: 4px 12px; }}
dt {{ color: #9ca3af; }}
.topics span {{ display: inline-block; margin: 0 4px 4px 0; padding: 2px 8px; border-radius: 999px; background: #1f2937; font-size: 12px; }}
</style>
</head>
<body>
<main>
  <p><a href="/">← OSS Radar home</a></p>
  <h1>{h(title)}</h1>
  <p>{h(description)}</p>
  {repo_items(repos)}
</main>
</body>
</html>
"""


def write_page(path: str, title: str, description: str, repos: list[dict]) -> str:
    out = SITE / path.strip("/") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(title, description, f"/{path.strip('/')}/", repos))
    return f"/{path.strip('/')}/"


def write_sitemap(urls: list[str]) -> None:
    now = datetime.now(timezone.utc).date().isoformat()
    entries = []
    for url in sorted(set(urls)):
        loc = f"{BASE_URL}{url}" if url.startswith("/") else url
        entries.append(f"  <url><loc>{xml_escape(loc)}</loc><lastmod>{now}</lastmod></url>")
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def write_robots() -> None:
    (SITE / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://radar.aegismemory.com/sitemap.xml\n"
    )


def write_feeds(data: dict) -> None:
    feeds = SITE / "feeds"
    feeds.mkdir(exist_ok=True)
    updated = data.get("last_updated", datetime.now(timezone.utc).isoformat())

    def rss(name: str, title: str, repos: list[dict]) -> str:
        items = []
        for repo in repos[:30]:
            items.append(
                f"""<item><title>{xml_escape(repo.get('name', ''))}</title><link>{xml_escape(repo.get('url', ''))}</link><description>{xml_escape(repo.get('description') or '')}</description><guid>{xml_escape(repo.get('url', ''))}</guid></item>"""
            )
        content = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel>'
            f'<title>{xml_escape(title)}</title><link>{BASE_URL}/</link>'
            f'<description>OSS Radar {xml_escape(name)} feed</description><lastBuildDate>{xml_escape(updated)}</lastBuildDate>'
            + "".join(items)
            + '</channel></rss>\n'
        )
        return content

    (SITE / "feed.xml").write_text(rss("main", "OSS Radar updates", data.get("trending", [])))
    (feeds / "trending.xml").write_text(rss("trending", "OSS Radar trending repositories", data.get("trending", [])))
    (feeds / "gems.xml").write_text(rss("gems", "OSS Radar underrated gems", data.get("gems", [])))
    cats = {}
    for repo in data.get("trending", []) + data.get("gems", []):
        cats.setdefault(repo.get("category", "dev-tools"), []).append(repo)
    for cat, repos in cats.items():
        (feeds / f"{cat}.xml").write_text(rss(cat, f"OSS Radar {cat.replace('-', ' ')}", repos))


def main() -> None:
    data = load_data()
    urls = ["/"]
    urls.append(write_page("trending", "Trending AI open-source repositories", "Fast-moving AI GitHub projects tracked by OSS Radar.", data.get("trending", [])))
    urls.append(write_page("gems", "Underrated AI open-source gems", "Lower-visibility AI repositories with strong quality and maintenance signals.", data.get("gems", [])))
    urls.append(write_page("abandoned", "Potentially abandoned AI open-source repositories", "Popular AI repositories with stale maintenance signals to review before adopting.", data.get("abandoned", [])))
    categories = {}
    for repo in data.get("trending", []) + data.get("gems", []) + data.get("abandoned", []):
        categories.setdefault(repo.get("category", "dev-tools"), []).append(repo)
    for cat, repos in categories.items():
        urls.append(write_page(f"categories/{cat}", f"{cat.replace('-', ' ').title()} AI repositories", f"OSS Radar projects in the {cat.replace('-', ' ')} category.", repos))
    write_robots()
    write_sitemap(urls)
    write_feeds(data)
    print(f"Generated {len(urls)} crawlable pages, sitemap, robots.txt, and feeds")


if __name__ == "__main__":
    main()
