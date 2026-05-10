"""
OSS Radar — AI Stack Intelligence Collector
Fetches AI-related GitHub repos, computes trending + gem scores,
writes data.json for the static frontend.

Zero cost: runs via GitHub Actions cron, stores data as JSON in the repo.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

API_BASE = "https://api.github.com"

# AI stack topics to scan
SEARCH_TOPICS = [
    "llm", "ai-agent", "ai-agents", "mcp", "mcp-server",
    "rag", "langchain", "langgraph", "crewai",
    "vector-database", "fine-tuning", "lora",
    "generative-ai", "ai-tools", "llm-inference",
    "prompt-engineering", "ai-framework", "embeddings",
    "vllm", "ollama", "transformers", "ai-safety",
    "agent-framework", "model-serving", "mlops",
]

# Category mapping — assign categories based on topic matches
CATEGORY_MAP = {
    "agent-framework": ["ai-agent", "ai-agents", "agent-framework", "crewai", "langgraph", "autogen"],
    "model-serving": ["llm-inference", "vllm", "ollama", "model-serving", "gguf", "quantization"],
    "rag-and-search": ["rag", "vector-database", "embeddings", "semantic-search", "langchain"],
    "fine-tuning": ["fine-tuning", "lora", "qlora", "peft", "training"],
    "mcp": ["mcp", "mcp-server", "model-context-protocol"],
    "dev-tools": ["ai-tools", "ai-framework", "prompt-engineering", "ai-coding"],
    "safety-and-evals": ["ai-safety", "ai-evaluation", "guardrails", "red-teaming"],
    "mlops": ["mlops", "ml-pipeline", "model-monitoring", "feature-store"],
}

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "site"
DATA_FILE = DATA_DIR / "data.json"
HISTORY_FILE = DATA_DIR / "history.json"

# Thresholds
GEM_STAR_CEILING = 500          # max stars to qualify as "underrated"
ABANDONED_DAYS = 30             # no push in N days = flagged
MIN_STARS_FOR_TRENDING = 50     # ignore very tiny repos in trending
MAX_REPOS_PER_QUERY = 80        # results per search topic
DETAIL_FETCH_LIMIT = 250        # max repos to fetch commit/contributor data for


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------

_request_count = 0

def gh_get(url: str, params: dict = None) -> dict | list | None:
    """GET from GitHub API with rate-limit awareness."""
    global _request_count
    _request_count += 1

    # Respect search rate limit (30/min authenticated)
    if _request_count % 28 == 0:
        time.sleep(5)

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 403:
            reset = resp.headers.get("X-RateLimit-Reset")
            if reset:
                wait = max(int(reset) - int(time.time()), 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(min(wait, 60))
                resp = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if resp.status_code == 200:
            return resp.json()

        print(f"  Warning: {url} returned {resp.status_code}")
        return None

    except requests.RequestException as e:
        print(f"  Error: {e}")
        return None


def search_repos(query: str, sort: str = "stars", per_page: int = 30) -> list[dict]:
    """Search GitHub repos. Returns list of repo dicts."""
    url = f"{API_BASE}/search/repositories"
    params = {
        "q": query,
        "sort": sort,
        "order": "desc",
        "per_page": min(per_page, 100),
    }
    data = gh_get(url, params)
    if data and "items" in data:
        return data["items"]
    return []


def get_repo_details(owner: str, repo: str) -> dict | None:
    """Fetch full repo details."""
    return gh_get(f"{API_BASE}/repos/{owner}/{repo}")


def get_commit_count_recent(owner: str, repo: str, days: int = 30) -> int:
    """Count commits in the last N days."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    data = gh_get(
        f"{API_BASE}/repos/{owner}/{repo}/commits",
        params={"since": since, "per_page": 1},
    )
    # The API doesn't return total count directly, but we can check
    # if there are commits and approximate from pagination
    if data is None:
        return 0
    if isinstance(data, list):
        # Fetch up to 100 to get a count
        data_full = gh_get(
            f"{API_BASE}/repos/{owner}/{repo}/commits",
            params={"since": since, "per_page": 100},
        )
        return len(data_full) if isinstance(data_full, list) else 0
    return 0


def get_contributor_count(owner: str, repo: str) -> int:
    """Count unique contributors (up to 100)."""
    data = gh_get(
        f"{API_BASE}/repos/{owner}/{repo}/contributors",
        params={"per_page": 100, "anon": "false"},
    )
    if isinstance(data, list):
        return len(data)
    return 1


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def assign_category(topics: list[str]) -> str:
    """Map repo topics to a category."""
    topic_set = set(t.lower() for t in topics)
    best_cat = "dev-tools"
    best_score = 0
    for cat, keywords in CATEGORY_MAP.items():
        score = len(topic_set.intersection(keywords))
        if score > best_score:
            best_score = score
            best_cat = cat
    return best_cat


def compute_gem_score(repo: dict, commits_30d: int, contributors: int) -> float:
    """
    Compute the underrated gem score (0.0 - 1.0).
    High score = high quality, low visibility.

    Weights:
      30% commit velocity
      20% issue engagement (open_issues / stars ratio, capped)
      15% star acceleration (stars / age in days)
      15% contributor diversity
      10% docs signal (description length + has topics)
      10% recency of last push
    """
    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))

    age_days = max((now - created).days, 1)
    days_since_push = (now - pushed).days
    stars = max(repo.get("stargazers_count", 0), 1)
    open_issues = repo.get("open_issues_count", 0)
    topics = repo.get("topics", [])
    description = repo.get("description", "") or ""

    # 1. Commit velocity (30%) — commits per week, normalized
    commits_per_week = (commits_30d / 4.3) if commits_30d > 0 else 0
    commit_score = min(commits_per_week / 15, 1.0)  # 15 commits/week = max

    # 2. Issue engagement (20%) — shows community interest
    issue_ratio = open_issues / stars
    issue_score = min(issue_ratio / 0.5, 1.0)  # 0.5 issues per star = max

    # 3. Star acceleration (15%) — stars per day of existence
    stars_per_day = stars / age_days
    accel_score = min(stars_per_day / 5, 1.0)  # 5 stars/day = max

    # 4. Contributor diversity (15%)
    contrib_score = min(contributors / 10, 1.0)  # 10 contributors = max

    # 5. Docs signal (10%)
    has_good_desc = 1.0 if len(description) > 80 else len(description) / 80
    has_topics = 1.0 if len(topics) >= 3 else len(topics) / 3
    docs_score = (has_good_desc + has_topics) / 2

    # 6. Recency (10%)
    recency_score = max(1.0 - (days_since_push / 14), 0.0)  # pushed in last 2 weeks = max

    gem_score = (
        0.30 * commit_score
        + 0.20 * issue_score
        + 0.15 * accel_score
        + 0.15 * contrib_score
        + 0.10 * docs_score
        + 0.10 * recency_score
    )

    return round(min(gem_score, 1.0), 3)


# ---------------------------------------------------------------------------
# History tracking (for star deltas)
# ---------------------------------------------------------------------------

def load_history() -> dict:
    """Load historical star counts."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"snapshots": []}


def save_history(history: dict):
    """Save historical star counts."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def compute_star_deltas(repos: dict[str, int], history: dict) -> dict[str, dict]:
    """
    Compare current star counts with historical snapshots.
    Returns {full_name: {delta_3d, delta_7d, delta_30d}}.
    """
    deltas = {}
    now = datetime.now(timezone.utc)
    snapshots = history.get("snapshots", [])

    for name, current_stars in repos.items():
        d = {"delta_3d": 0, "delta_7d": 0, "delta_30d": 0}
        for snap in reversed(snapshots):
            snap_time = datetime.fromisoformat(snap["timestamp"])
            age = (now - snap_time).days
            snap_stars = snap.get("stars", {}).get(name, current_stars)

            if age >= 3 and d["delta_3d"] == 0:
                d["delta_3d"] = current_stars - snap_stars
            if age >= 7 and d["delta_7d"] == 0:
                d["delta_7d"] = current_stars - snap_stars
            if age >= 30 and d["delta_30d"] == 0:
                d["delta_30d"] = current_stars - snap_stars
                break

        deltas[name] = d
    return deltas


# ---------------------------------------------------------------------------
# Main collection pipeline
# ---------------------------------------------------------------------------

def collect():
    """Run the full collection pipeline."""
    print(f"=== OSS Radar Collection — {datetime.now(timezone.utc).isoformat()} ===")
    print(f"  Token configured: {'yes' if GITHUB_TOKEN else 'NO (rate limits will be tight)'}")

    now = datetime.now(timezone.utc)
    thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    # -----------------------------------------------------------------------
    # Step 1: Search for AI repos across all topics
    # -----------------------------------------------------------------------
    print("\n[1/5] Searching GitHub for AI stack repos...")
    seen = set()
    all_repos = []

    for topic in SEARCH_TOPICS:
        query = f"topic:{topic} pushed:>{thirty_days_ago} stars:>=5"
        results = search_repos(query, sort="stars", per_page=MAX_REPOS_PER_QUERY)
        for repo in results:
            name = repo["full_name"]
            if name not in seen:
                seen.add(name)
                all_repos.append(repo)
        print(f"  topic:{topic} → {len(results)} results ({len(seen)} unique total)")
        time.sleep(2)  # stay within search rate limit

    print(f"  Total unique repos collected: {len(all_repos)}")

    # -----------------------------------------------------------------------
    # Step 2: Fetch detailed data for top candidates
    # -----------------------------------------------------------------------
    print("\n[2/5] Fetching commit & contributor data...")
    repo_details = {}
    fetch_candidates = sorted(all_repos, key=lambda r: r.get("stargazers_count", 0))
    fetch_candidates = fetch_candidates[:DETAIL_FETCH_LIMIT]

    for i, repo in enumerate(fetch_candidates):
        owner, name = repo["full_name"].split("/", 1)

        commits = get_commit_count_recent(owner, name, days=30)
        contributors = get_contributor_count(owner, name)

        repo_details[repo["full_name"]] = {
            "commits_30d": commits,
            "contributors": contributors,
        }

        if (i + 1) % 25 == 0:
            print(f"  Processed {i + 1}/{len(fetch_candidates)} repos")
            time.sleep(2)

    # -----------------------------------------------------------------------
    # Step 3: Compute scores and classify
    # -----------------------------------------------------------------------
    print("\n[3/5] Computing scores...")
    trending = []
    gems = []
    abandoned = []

    current_stars = {}

    for repo in all_repos:
        full_name = repo["full_name"]
        stars = repo.get("stargazers_count", 0)
        current_stars[full_name] = stars

        topics = repo.get("topics", [])
        details = repo_details.get(full_name, {"commits_30d": 0, "contributors": 1})

        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        days_since_push = (now - pushed).days

        gem_score = compute_gem_score(repo, details["commits_30d"], details["contributors"])
        category = assign_category(topics)

        entry = {
            "name": full_name,
            "description": (repo.get("description") or "")[:200],
            "stars": stars,
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "language": repo.get("language") or "Unknown",
            "topics": topics[:8],
            "category": category,
            "created_at": repo.get("created_at", ""),
            "pushed_at": repo.get("pushed_at", ""),
            "days_since_push": days_since_push,
            "commits_30d": details["commits_30d"],
            "contributors": details["contributors"],
            "gem_score": gem_score,
            "url": repo.get("html_url", ""),
            "owner_avatar": repo.get("owner", {}).get("avatar_url", ""),
        }

        # Classify
        if days_since_push > ABANDONED_DAYS and stars >= 200:
            entry["abandoned_flag"] = True
            abandoned.append(entry)

        if stars <= GEM_STAR_CEILING and gem_score >= 0.3:
            gems.append(entry)

        if stars >= MIN_STARS_FOR_TRENDING:
            trending.append(entry)

    # Sort
    trending.sort(key=lambda r: r["stars"], reverse=True)
    gems.sort(key=lambda r: r["gem_score"], reverse=True)
    abandoned.sort(key=lambda r: r["stars"], reverse=True)

    # Limit output
    trending = trending[:60]
    gems = gems[:30]
    abandoned = abandoned[:20]

    # -----------------------------------------------------------------------
    # Step 4: Compute star deltas from history
    # -----------------------------------------------------------------------
    print("\n[4/5] Computing star deltas...")
    history = load_history()
    deltas = compute_star_deltas(current_stars, history)

    for lst in [trending, gems, abandoned]:
        for entry in lst:
            d = deltas.get(entry["name"], {})
            entry["stars_delta_3d"] = d.get("delta_3d", 0)
            entry["stars_delta_7d"] = d.get("delta_7d", 0)
            entry["stars_delta_30d"] = d.get("delta_30d", 0)

    # Save new snapshot
    history["snapshots"].append({
        "timestamp": now.isoformat(),
        "stars": current_stars,
    })
    # Keep only last 35 days of snapshots
    cutoff = (now - timedelta(days=35)).isoformat()
    history["snapshots"] = [
        s for s in history["snapshots"] if s["timestamp"] > cutoff
    ]
    save_history(history)

    # -----------------------------------------------------------------------
    # Step 5: Write data.json
    # -----------------------------------------------------------------------
    print("\n[5/5] Writing data.json...")
    output = {
        "last_updated": now.isoformat(),
        "stats": {
            "total_scanned": len(all_repos),
            "trending_count": len(trending),
            "gems_count": len(gems),
            "abandoned_count": len(abandoned),
        },
        "trending": trending,
        "gems": gems,
        "abandoned": abandoned,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Done. {len(trending)} trending, {len(gems)} gems, {len(abandoned)} abandoned.")
    print(f"  Data written to {DATA_FILE}")
    print(f"  Total API requests: {_request_count}")


if __name__ == "__main__":
    collect()
