"""
OSS Radar — AI Stack Intelligence Collector
Fetches AI-related GitHub repos, computes trending + gem scores,
writes data.json for the static frontend.

Zero cost: runs via GitHub Actions cron, stores data as JSON in the repo.
"""

import json
import os
import re
import statistics
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
    "llm-evaluation", "llm-testing", "eval-framework", "red-teaming",
    "local-llm", "edge-ai", "on-device-ai", "llama-cpp",
    "llm-gateway", "ai-gateway", "llm-router", "model-router",
    "ai-security", "llm-security", "guardrails-ai", "prompt-injection",
    "ai-coding-assistant", "code-assistant", "copilot", "code-generation",
    "ai-webui", "llm-ui", "chat-ui", "stable-diffusion-webui",
    "multimodal-ai", "text-to-image", "text-to-video", "speech-to-text",
    "vector-store", "data-pipeline", "feature-store", "data-engineering",
]

# Category mapping — assign categories based on topic matches.  The insertion
# order is the tie-breaker, so narrowly scoped categories deliberately precede
# broad framework/tooling categories. Keep this taxonomy in sync with
# validate_site.py and README.md.
CATEGORY_MAP = {
    "mcp": ["mcp", "mcp-server", "model-context-protocol"],
    "ai-security-and-guardrails": ["ai-security", "llm-security", "ai-safety", "guardrails", "guardrails-ai", "prompt-injection", "red-teaming", "model-security"],
    "evals-and-testing": ["ai-evaluation", "llm-evaluation", "llm-testing", "eval-framework", "model-evaluation", "benchmarking", "observability"],
    "gateways-and-routing": ["llm-gateway", "ai-gateway", "llm-router", "model-router", "api-gateway", "litellm", "load-balancing"],
    "ai-coding-and-assistants": ["ai-coding", "ai-coding-assistant", "coding-assistant", "code-assistant", "code-generation", "copilot", "developer-assistant"],
    "ai-webui-and-interfaces": ["ai-webui", "llm-ui", "chat-ui", "webui", "stable-diffusion-webui", "gradio", "streamlit"],
    "multimodal-media": ["multimodal-ai", "text-to-image", "image-generation", "text-to-video", "video-generation", "speech-to-text", "text-to-speech", "audio-generation"],
    "vector-dbs-and-data": ["vector-database", "vector-store", "feature-store", "data-pipeline", "data-engineering", "ml-pipeline", "data-infrastructure", "etl"],
    "local-and-edge-ai": ["local-llm", "edge-ai", "on-device-ai", "llama-cpp", "gguf", "mlx", "webgpu", "ollama"],
    "fine-tuning": ["fine-tuning", "lora", "qlora", "peft", "model-training", "instruction-tuning"],
    "model-serving": ["llm-inference", "vllm", "model-serving", "inference-server", "model-deployment", "triton-inference-server", "quantization", "mlops"],
    "rag-and-search": ["rag", "retrieval-augmented-generation", "embeddings", "semantic-search", "neural-search", "document-retrieval"],
    "agent-framework": ["ai-agent", "ai-agents", "agent-framework", "crewai", "langgraph", "autogen", "multi-agent"],
    "dev-tools": ["ai-tools", "ai-framework", "prompt-engineering", "llm", "generative-ai", "langchain", "developer-tools", "mlops"],
}

# Name and description are intentionally *not* treated as bags of words.  Only
# these reviewed phrases may contribute text evidence.  This prevents incidental
# mentions (most notably "supports MCP") from becoming a product's identity.
CATEGORY_TEXT_RULES = {
    "mcp": ["mcp server", "model context protocol server", "mcp implementation"],
    "ai-security-and-guardrails": ["llm security", "ai guardrails", "prompt injection"],
    "evals-and-testing": ["llm evaluation", "ai evaluation", "eval framework"],
    "gateways-and-routing": ["llm gateway", "ai gateway", "model router", "llm proxy"],
    "ai-coding-and-assistants": ["coding assistant", "code assistant", "ai pair programmer"],
    "ai-webui-and-interfaces": ["web ui for llm", "llm web ui", "chat interface", "ai webui"],
    "multimodal-media": ["text to image", "text-to-image", "speech to text"],
    "vector-dbs-and-data": ["vector database", "vector store", "data pipeline"],
    "local-and-edge-ai": ["run llms locally", "on-device ai", "local llm"],
    "fine-tuning": ["fine tuning", "fine-tuning", "lora training"],
    "model-serving": ["inference server", "model serving", "llm inference"],
    "rag-and-search": ["retrieval augmented generation", "semantic search", "rag framework"],
    "agent-framework": ["agent framework", "multi-agent framework", "ai agent framework"],
    "dev-tools": ["developer tool", "automation platform", "workflow automation", "documentation"],
}

MCP_INTEGRATION_PHRASES = ("supports mcp", "mcp support", "mcp integration", "integrates with mcp")

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "site"
DATA_FILE = DATA_DIR / "data.json"
HISTORY_FILE = DATA_DIR / "history.json"

# Thresholds
GEM_STAR_CEILING = 500          # max stars to qualify as "underrated"
# Maintenance risk is intentionally not decided by one push-age cutoff.  This
# value remains only as the active-repository boundary for trending rankings.
TRENDING_ACTIVE_DAYS = 30
MIN_STARS_FOR_TRENDING = 50     # ignore very tiny repos in trending
MAX_REPOS_PER_QUERY = 80        # results per search topic
DETAIL_FETCH_LIMIT = 250        # max repos to fetch commit/contributor data for
TRENDING_RANK_LIMIT = 60        # retained independently for each history window
TRENDING_WINDOWS = (3, 7, 30)
DETAIL_FETCH_BUCKET_LIMITS = {     # reserve detail capacity for each display bucket
    "abandoned": 40,
    "gems": 70,
    "trending": 140,
}
ABANDONED_FETCH_LIMIT = 120      # maintenance-risk candidates per topic search


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


def get_commit_count_recent(owner: str, repo: str, days: int = 30,
                            include_automation: bool = False) -> tuple:
    """Return a recent commit lower bound and whether the 100-item result was capped."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    data = gh_get(
        f"{API_BASE}/repos/{owner}/{repo}/commits",
        params={"since": since, "per_page": 1},
    )
    # The API doesn't return total count directly, but we can check
    # if there are commits and approximate from pagination
    if data is None:
        return (None, False, None) if include_automation else (None, False)
    if isinstance(data, list):
        # Fetch up to 100 to get a count
        data_full = gh_get(
            f"{API_BASE}/repos/{owner}/{repo}/commits",
            params={"since": since, "per_page": 100},
        )
        if not isinstance(data_full, list):
            return (None, False, None) if include_automation else (None, False)
        result = (len(data_full), len(data_full) == 100)
        if include_automation:
            automated = sum(_is_automated_commit(item) for item in data_full)
            return (*result, round(automated / len(data_full), 3) if data_full else 0.0)
        return result
    return (None, False, None) if include_automation else (None, False)


def _is_automated_commit(commit: dict) -> bool:
    """Recognize common bot identities without treating missing identity as automation."""
    author = commit.get("author") or {}
    git_author = (commit.get("commit") or {}).get("author") or {}
    identity = " ".join(str(author.get(key, "")) for key in ("login", "type"))
    identity += " " + " ".join(str(git_author.get(key, "")) for key in ("name", "email"))
    normalized = identity.lower()
    return (author.get("type") == "Bot" or "[bot]" in normalized
            or "dependabot" in normalized or "github-actions" in normalized)


def get_contributor_metrics(owner: str, repo: str) -> dict:
    """Return lifetime contributor lower bound and contribution concentration."""
    data = gh_get(
        f"{API_BASE}/repos/{owner}/{repo}/contributors",
        params={"per_page": 100, "anon": "false"},
    )
    if isinstance(data, list):
        contributions = [item.get("contributions", 0) for item in data]
        total = sum(contributions)
        return {
            "contributors_total_lower_bound": len(data),
            "contributors_capped": len(data) == 100,
            "top_contributor_share": round(max(contributions) / total, 3) if total else None,
        }
    return {"contributors_total_lower_bound": None, "contributors_capped": False,
            "top_contributor_share": None}


def get_decision_signals(owner: str, repo: str, now: datetime | None = None) -> dict:
    """Fetch bounded release and response-activity signals; preserve API failures as missing."""
    now = now or datetime.now(timezone.utc)
    releases = gh_get(f"{API_BASE}/repos/{owner}/{repo}/releases", params={"per_page": 5})
    release_age = None
    release_cadence = None
    published_dates = [datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                       for item in releases if item.get("published_at")] if isinstance(releases, list) else []
    if published_dates:
        published = published_dates[0]
        release_age = max((now - published).days, 0)
        if len(published_dates) > 1:
            release_cadence = round(statistics.median(
                (published_dates[i] - published_dates[i + 1]).days
                for i in range(len(published_dates) - 1)), 1)

    since = (now - timedelta(days=30)).isoformat()
    issue_comments = gh_get(f"{API_BASE}/repos/{owner}/{repo}/issues/comments",
                            params={"since": since, "per_page": 100})
    review_comments = gh_get(f"{API_BASE}/repos/{owner}/{repo}/pulls/comments",
                             params={"since": since, "per_page": 100})
    recent_issues = gh_get(f"{API_BASE}/repos/{owner}/{repo}/issues",
                           params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 100})
    community = gh_get(f"{API_BASE}/repos/{owner}/{repo}/community/profile")
    workflows = gh_get(f"{API_BASE}/repos/{owner}/{repo}/actions/workflows", params={"per_page": 1})
    issue_activity = len(issue_comments) if isinstance(issue_comments, list) else None
    pr_activity = len(review_comments) if isinstance(review_comments, list) else None
    response_capped = any(isinstance(value, list) and len(value) == 100
                          for value in (issue_comments, review_comments))
    maintainer_responses = None if issue_activity is None and pr_activity is None else (issue_activity or 0) + (pr_activity or 0)
    closed_30d = opened_30d = None
    median_response_hours = None
    if isinstance(recent_issues, list):
        issues = [item for item in recent_issues if "pull_request" not in item]
        opened_30d = sum(item.get("created_at", "") >= since for item in issues)
        closed_30d = sum(bool(item.get("closed_at") and item["closed_at"] >= since) for item in issues)
        if isinstance(issue_comments, list):
            created = {item.get("url"): datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
                       for item in issues if item.get("url") and item.get("created_at")}
            first = {}
            for comment in issue_comments:
                issue_url = comment.get("issue_url")
                if issue_url in created and comment.get("created_at"):
                    timestamp = datetime.fromisoformat(comment["created_at"].replace("Z", "+00:00"))
                    first[issue_url] = min(first.get(issue_url, timestamp), timestamp)
            elapsed = [(timestamp - created[url]).total_seconds() / 3600
                       for url, timestamp in first.items() if timestamp >= created[url]]
            if elapsed:
                median_response_hours = round(statistics.median(elapsed), 1)
    documentation = None
    if isinstance(community, dict):
        documentation = min(max(community.get("health_percentage", 0) / 100, 0), 1)
    test_ci = None if not isinstance(workflows, dict) else workflows.get("total_count", 0) > 0
    return {"latest_release_age_days": release_age, "release_cadence_days": release_cadence,
            "documentation_completeness": documentation, "test_ci_present": test_ci,
            "issue_responses_30d_lower_bound": issue_activity,
            "pull_request_responses_30d_lower_bound": pr_activity,
            "maintainer_responses_30d_lower_bound": maintainer_responses,
            "issues_closed_30d_lower_bound": closed_30d,
            "open_issue_growth_30d": None if opened_30d is None else opened_30d - closed_30d,
            "median_issue_response_hours": median_response_hours,
            "response_activity_capped": response_capped}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def assign_category(topics: list[str], name: str = "", description: str = "",
                    return_details: bool = False) -> str | dict:
    """Classify primary function from curated evidence, optionally returning its audit trail."""
    topic_set = {str(t).lower() for t in topics}
    text = f"{name} {description}".lower().replace("_", " ")
    scores = {cat: 0 for cat in CATEGORY_MAP}
    reasons = {cat: [] for cat in CATEGORY_MAP}

    for cat, keywords in CATEGORY_MAP.items():
        matched = sorted(topic_set.intersection(keywords))
        scores[cat] += len(matched) * (1 if cat == "dev-tools" else 3)
        reasons[cat].extend(f"topic:{keyword}" for keyword in matched)
        for phrase in CATEGORY_TEXT_RULES[cat]:
            if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text):
                scores[cat] += 2
                reasons[cat].append(f"text:{phrase}")

    # A docs repository is documentation, even when it documents MCP.  Likewise
    # an integration mention can be secondary evidence but cannot define a tool.
    repo_slug = name.lower().rstrip("/").split("/")[-1]
    is_docs = repo_slug in {"docs", "documentation"} or "documentation repository" in text
    if is_docs:
        scores["dev-tools"] = max(scores["dev-tools"], 5)
        reasons["dev-tools"].append("identity:documentation-repository")
    if any(phrase in text for phrase in MCP_INTEGRATION_PHRASES):
        scores["mcp"] = min(scores["mcp"], 2)
        reasons["mcp"] = [reason for reason in reasons["mcp"] if not reason.startswith("text:")]
        reasons["mcp"].append("integration:mcp")

    ranked = sorted(scores, key=lambda cat: (-scores[cat], list(CATEGORY_MAP).index(cat)))
    primary = "dev-tools" if scores[ranked[0]] == 0 else ranked[0]
    primary_score = scores[primary]
    secondary = [cat for cat in ranked if cat != primary and scores[cat] >= 3
                 and scores[cat] >= primary_score * .5][:2]
    runner_up = max((scores[cat] for cat in CATEGORY_MAP if cat != primary), default=0)
    confidence = round(min(.98, .45 + .09 * primary_score + .04 * max(primary_score - runner_up, 0)), 2)
    if primary_score == 0:
        confidence = .35
        reasons[primary] = ["fallback:no-category-specific-match"]
    result = {"category": primary, "secondary_categories": secondary,
              "category_confidence": confidence, "category_reasons": reasons[primary]}
    return result if return_details else primary


def compute_gem_score(repo: dict, commits_30d: int, contributors: int,
                      signals: dict | None = None, return_details: bool = False) -> float | dict:
    """
    Compute activity, quality, and visibility subscores for underrated gems.

    Open issue volume is never rewarded. When available, closure/response
    activity, response time, and issue growth describe issue maintenance.
    """
    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))

    days_since_push = (now - pushed).days
    stars = max(repo.get("stargazers_count", 0), 1)
    open_issues = repo.get("open_issues_count", 0)
    topics = repo.get("topics", [])
    description = repo.get("description", "") or ""

    signals = signals or {}
    automation = signals.get("automated_commit_share") or 0
    human_commits = commits_30d * max(0, 1 - automation)
    velocity = min((human_commits / 4.3) / 12, 1.0)
    diversity = min(contributors / 10, 1.0)
    concentration = signals.get("top_contributor_share")
    distribution = diversity if concentration is None else max(0, 1 - concentration)
    commit_community = velocity * (.55 + .45 * distribution)
    recency = max(1.0 - days_since_push / 45, 0.0)
    commits_180d = signals.get("commits_180d_lower_bound")
    consistency = recency if commits_180d is None else min(commits_30d / max(commits_180d / 6, 1), 1)
    release_age = signals.get("latest_release_age_days")
    release_recency = recency if release_age is None else max(1 - release_age / 365, 0)
    activity = .55 * commit_community + .25 * recency + .20 * consistency

    has_good_desc = 1.0 if len(description) > 80 else len(description) / 80
    has_topics = 1.0 if len(topics) >= 3 else len(topics) / 3
    docs = signals.get("documentation_completeness")
    if docs is None:
        docs = (has_good_desc + has_topics) / 2
    license_value = repo.get("license")
    spdx = license_value.get("spdx_id") if isinstance(license_value, dict) else license_value
    license_score = 1.0 if spdx and spdx != "NOASSERTION" else 0.0
    test_ci = signals.get("test_ci_present")
    quality_basics = (.45 * docs + .30 * license_score + .25 * (test_ci if test_ci is not None else .5))

    issue_parts = []
    responses = signals.get("maintainer_responses_30d_lower_bound")
    closures = signals.get("issues_closed_30d_lower_bound")
    response_hours = signals.get("median_issue_response_hours")
    growth = signals.get("open_issue_growth_30d")
    if responses is not None: issue_parts.append(min(responses / 10, 1))
    if closures is not None: issue_parts.append(min(closures / 10, 1))
    if response_hours is not None: issue_parts.append(max(1 - response_hours / (24 * 14), 0))
    if growth is not None: issue_parts.append(max(1 - max(growth, 0) / 20, 0))
    # With no richer issue inputs, unresolved pressure can only hurt, never help.
    issue_health = (sum(issue_parts) / len(issue_parts) if issue_parts
                    else max(1 - (open_issues / stars), 0))
    cadence_days = signals.get("release_cadence_days")
    release_quality = release_recency if cadence_days is None else (
        .6 * release_recency + .4 * max(1 - cadence_days / 365, 0))
    quality = .55 * quality_basics + .30 * issue_health + .15 * release_quality
    visibility = max(0, min(1, 1 - repo.get("stargazers_count", 0) / GEM_STAR_CEILING))
    score = round(min(.40 * activity + .40 * quality + .20 * visibility, 1), 3)
    subscores = {"activity": round(activity, 3), "quality": round(quality, 3),
                 "visibility": round(visibility, 3)}
    ranked = sorted(subscores, key=subscores.get, reverse=True)
    labels = {"activity": "consistent human and community activity",
              "quality": "healthy maintenance and project fundamentals",
              "visibility": "strong signals despite limited visibility"}
    reasons = [labels[name] for name in ranked if subscores[name] >= .55][:2]
    if growth is not None and growth <= 0: reasons.append("open issue backlog is stable or shrinking")
    if not reasons: reasons = ["limited evidence; inspect maintenance signals before adopting"]
    result = {"gem_score": score, "gem_subscores": subscores, "gem_reasons": reasons[:3]}
    return result if return_details else score


def compute_adoption_readiness(repo: dict, signals: dict) -> dict:
    """Compute an uncalibrated readiness heuristic, not a probability or percentage."""
    now = datetime.now(timezone.utc)
    pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since_push = max((now - pushed).days, 0)
    stars = max(repo.get("stargazers_count", 0), 1)
    forks = repo.get("forks_count", 0)
    open_issues = repo.get("open_issues_count", 0)
    topics = repo.get("topics", [])

    recency = max(1.0 - days_since_push / 60, 0.0)
    commits = signals.get("commits_30d_lower_bound")
    contributors = signals.get("contributors_total_lower_bound")
    velocity = min(commits / 30, 1.0) if commits is not None else None
    diversity = min(contributors / 12, 1.0) if contributors is not None else None
    issue_health = max(1.0 - min(open_issues / stars, 1.0), 0.0)
    fork_signal = min((forks / stars) / 0.25, 1.0)
    docs_signal = min(len(topics) / 5, 1.0)
    spdx = (repo.get("license") or {}).get("spdx_id")
    permissive = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense"}
    license_signal = 1.0 if spdx in permissive else 0.55 if spdx else 0.35
    release_age = signals.get("latest_release_age_days")
    release_signal = None if release_age is None else max(1 - release_age / 365, 0)
    issue_responses = signals.get("issue_responses_30d_lower_bound")
    pr_responses = signals.get("pull_request_responses_30d_lower_bound")
    response = None if issue_responses is None and pr_responses is None else (issue_responses or 0) + (pr_responses or 0)
    response_signal = None if response is None else min(response / 10, 1)
    concentration = signals.get("top_contributor_share")
    concentration_signal = None if concentration is None else 1 - concentration
    parts = {"push_recency": (recency, .20), "commit_activity": (velocity, .18),
             "contributor_breadth": (diversity, .13), "issue_load": (issue_health, .10),
             "fork_interest": (fork_signal, .07), "documentation": (docs_signal, .06),
             "license": (license_signal, .10), "release_recency": (release_signal, .06),
             "response_activity": (response_signal, .05),
             "maintenance_distribution": (concentration_signal, .05)}
    available_weight = sum(weight for value, weight in parts.values() if value is not None)
    score = sum(value * weight for value, weight in parts.values() if value is not None) / available_weight
    if repo.get("archived"):
        score = 0
    score = round(score * 100)  # points, explicitly not a calibrated percentage
    label = "ready" if score >= 72 else "needs review" if score >= 45 else "high risk"
    missing = [name for name, (value, _) in parts.items() if value is None]
    positives = [name.replace("_", " ") for name, (value, _) in parts.items() if value is not None and value >= .7][:3]
    risks = (["repository is archived"] if repo.get("archived") else [])
    if release_age is not None and release_age > 365: risks.append(f"latest release is {release_age} days old")
    if concentration is not None and concentration >= .8: risks.append("maintenance is concentrated in one contributor")
    confidence = "high" if not missing else "medium" if len(missing) <= 2 else "low"
    return {"adoption_score": score, "adoption_label": label, "score_breakdown": {
                name: (None if value is None else round(value * 100)) for name, (value, _) in parts.items()},
            "data_confidence": confidence, "positive_signals": positives,
            "risk_signals": risks, "missing_inputs": missing}


def compute_adoption_score(repo: dict, commits_30d: int, contributors: int) -> tuple[int, str]:
    """Compatibility wrapper returning heuristic points and a qualitative label."""
    result = compute_adoption_readiness(repo, {"commits_30d_lower_bound": commits_30d,
        "contributors_total_lower_bound": contributors})
    return result["adoption_score"], result["adoption_label"]


def compute_maintainer_health(repo: dict, commits_30d: int | None, contributors: int | None) -> str:
    """Classify maintainer health using simple deterministic signals."""
    now = datetime.now(timezone.utc)
    pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since_push = (now - pushed).days
    if repo.get("archived") or days_since_push > 120:
        return "risky"
    if days_since_push > 45 or commits_30d == 0 or (contributors is not None and contributors <= 1):
        return "watch"
    return "healthy"


def classify_maintenance_risk(repo: dict, signals: dict, category: str,
                              now: datetime | None = None) -> dict:
    """Classify maintenance risk from multiple explainable signals.

    The score is a prioritisation heuristic, not a claim that a repository is
    abandoned.  Documentation, courses, and curated lists commonly have a
    deliberately slower cadence, so they receive substantially longer recency
    and release thresholds.
    """
    now = now or datetime.now(timezone.utc)
    pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
    days_since_push = max((now - pushed).days, 0)
    text = " ".join([repo.get("name", ""), repo.get("full_name", ""),
                     repo.get("description") or "", *repo.get("topics", [])]).lower()
    if any(word in text for word in ("awesome", "curated", "list of", "resources")):
        repo_type, push_threshold, release_threshold = "curated-list", 365, 730
    elif any(word in text for word in ("course", "curriculum", "tutorial", "workshop", "book")):
        repo_type, push_threshold, release_threshold = "course", 270, 540
    elif any(word in text for word in ("documentation", " docs", "docs-", "guide")):
        repo_type, push_threshold, release_threshold = "documentation", 180, 540
    else:
        repo_type, push_threshold, release_threshold = "software", 90, 365

    score = 0
    reasons = []
    observed = 1  # push age is always present
    possible = 6
    if repo.get("archived"):
        score += 70
        reasons.append("repository is archived")
    if days_since_push > push_threshold:
        score += min(30, 15 + round(15 * (days_since_push - push_threshold) / push_threshold))
        reasons.append(f"no push in {days_since_push} days")

    release_age = signals.get("latest_release_age_days")
    if release_age is not None:
        observed += 1
        if release_age > release_threshold:
            score += 12
            reasons.append(f"latest release is {release_age} days old")

    recent = signals.get("commits_30d_lower_bound")
    baseline = signals.get("commits_180d_lower_bound")
    if recent is not None and baseline is not None:
        observed += 1
        # The preceding five months form a rough historical monthly baseline.
        historical_monthly = max((baseline - recent) / 5, 0)
        if historical_monthly >= 2 and recent < historical_monthly * .25:
            score += 18
            reasons.append(f"recent commit cadence is {recent}/{historical_monthly:.1f} of its monthly baseline")

    open_issues = repo.get("open_issues_count")
    issue_responses = signals.get("issue_responses_30d_lower_bound")
    if open_issues is not None and issue_responses is not None:
        observed += 1
        pressure_threshold = 25 if repo_type == "software" else 75
        if open_issues >= pressure_threshold and issue_responses == 0:
            score += 18
            reasons.append(f"{open_issues} open issues with no maintainer issue responses in 30 days")

    pr_responses = signals.get("pull_request_responses_30d_lower_bound")
    if pr_responses is not None:
        observed += 1
        if pr_responses == 0 and (open_issues or 0) >= 10:
            score += 8
            reasons.append("no pull-request review responses in 30 days")

    maintainer_responses = signals.get("maintainer_responses_30d_lower_bound")
    if maintainer_responses is not None:
        observed += 1
        if maintainer_responses == 0 and (open_issues or 0) >= 10:
            score += 8
            reasons.append("no maintainer response activity in 30 days")

    score = min(score, 100)
    confidence = round(observed / possible, 2)
    return {"maintenance_risk_score": score, "risk_confidence": confidence,
            "risk_confidence_label": "high" if confidence >= .8 else "medium" if confidence >= .5 else "low",
            "repository_type": repo_type, "risk_reasons": reasons,
            "at_risk": bool(repo.get("archived")) or score >= 40}


def build_trend_reasons(entry: dict) -> list[str]:
    """Create deterministic explanations for why a repo is notable."""
    reasons = []
    if entry.get("stars_delta_7d") is not None and entry["stars_delta_7d"] > 0:
        reasons.append(f"+{entry['stars_delta_7d']:,} stars in 7 days")
    elif entry.get("stars_delta_30d") is not None and entry["stars_delta_30d"] > 0:
        reasons.append(f"+{entry['stars_delta_30d']:,} stars in 30 days")
    if (entry.get("commits_30d_lower_bound") or 0) >= 10:
        suffix = "+" if entry.get("commits_30d_capped") else ""
        reasons.append(f"{entry['commits_30d_lower_bound']}{suffix} commits in 30 days")
    if (entry.get("contributors_total_lower_bound") or 0) >= 5:
        suffix = "+" if entry.get("contributors_capped") else ""
        reasons.append(f"{entry['contributors_total_lower_bound']}{suffix} lifetime contributors")
    if not reasons:
        reasons.append(f"High-signal {entry['category'].replace('-', ' ')} project")
    return reasons[:2]


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


def compute_star_deltas(
    repos: dict[str, int], history: dict, now: datetime | None = None
) -> dict[str, dict]:
    """
    Compare current star counts with historical snapshots.
    A delta is valid only when the repository existed in a snapshot at least as
    old as the requested window. Missing history is represented by ``None`` --
    it is not zero growth.
    """
    deltas = {}
    now = now or datetime.now(timezone.utc)
    snapshots = history.get("snapshots", [])

    for name, current_stars in repos.items():
        repo_snapshots = [snap for snap in snapshots if name in snap.get("stars", {})]
        coverage_days = max(
            ((now - datetime.fromisoformat(snap["timestamp"])).total_seconds() / 86400
             for snap in repo_snapshots),
            default=0,
        )
        d = {"history_coverage_days": round(max(coverage_days, 0), 2)}
        for window in TRENDING_WINDOWS:
            d[f"delta_{window}d"] = None
            d[f"delta_{window}d_valid"] = False

        # Choose the closest snapshot at or beyond each boundary, rather than
        # whichever item happens to occur first in the history file.
        for snap in sorted(repo_snapshots, key=lambda item: item["timestamp"], reverse=True):
            snap_time = datetime.fromisoformat(snap["timestamp"])
            age = (now - snap_time).total_seconds() / 86400
            for window in TRENDING_WINDOWS:
                key = f"delta_{window}d"
                if age >= window and not d[f"{key}_valid"]:
                    d[key] = current_stars - snap["stars"][name]
                    d[f"{key}_valid"] = True

        deltas[name] = d
    return deltas


def rank_trending(entries: list[dict], window: int, limit: int = TRENDING_RANK_LIMIT) -> list[dict]:
    """Rank all history-eligible active repositories for one growth window."""
    delta_key = f"stars_delta_{window}d"
    valid_key = f"{delta_key}_valid"
    eligible = [
        entry for entry in entries
        if entry.get(valid_key)
        and not entry.get("archived", False)
        and entry.get("days_since_push", TRENDING_ACTIVE_DAYS + 1) <= TRENDING_ACTIVE_DAYS
    ]

    def rank_key(entry: dict) -> tuple:
        delta = entry[delta_key]
        previous_stars = max(entry["stars"] - delta, 1)
        relative_growth = delta / previous_stars
        # Delta is primary. Relative growth, push recency, total stars, and name
        # provide explicit and deterministic tie-breakers.
        return (-delta, -relative_growth, entry["days_since_push"], -entry["stars"], entry["name"].lower())

    return sorted(eligible, key=rank_key)[:limit]


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

    abandoned_candidates_seen = set()
    abandoned_candidates = []

    for topic in SEARCH_TOPICS:
        query = f"topic:{topic} pushed:>{thirty_days_ago} stars:>=5"
        results = search_repos(query, sort="stars", per_page=MAX_REPOS_PER_QUERY)
        for repo in results:
            name = repo["full_name"]
            if name not in seen:
                seen.add(name)
                all_repos.append(repo)
        print(f"  topic:{topic} → {len(results)} active results ({len(seen)} unique total)")
        time.sleep(2)  # stay within search rate limit

        stale_query = f"topic:{topic} pushed:<{thirty_days_ago} stars:>=200"
        stale_results = search_repos(stale_query, sort="stars", per_page=min(ABANDONED_FETCH_LIMIT, 100))
        for repo in stale_results:
            name = repo["full_name"]
            if name not in abandoned_candidates_seen:
                abandoned_candidates_seen.add(name)
                abandoned_candidates.append(repo)
            if name not in seen:
                seen.add(name)
                all_repos.append(repo)
        print(f"  topic:{topic} → {len(stale_results)} stale results ({len(abandoned_candidates_seen)} abandoned candidates)")
        time.sleep(2)

    print(f"  Total unique repos collected: {len(all_repos)}")
    print(f"  Abandoned candidates collected: {len(abandoned_candidates)}")

    # -----------------------------------------------------------------------
    # Step 2: Fetch detailed data for top candidates
    # -----------------------------------------------------------------------
    print("\n[2/5] Fetching commit & contributor data...")
    repo_details = {}

    def candidate_bucket(repo: dict) -> str | None:
        stars = repo.get("stargazers_count", 0)
        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        days_since_push = (now - pushed).days
        if days_since_push > TRENDING_ACTIVE_DAYS and stars >= 200:
            return "abandoned"
        if stars <= GEM_STAR_CEILING:
            return "gems"
        if stars >= MIN_STARS_FOR_TRENDING:
            return "trending"
        return None

    def candidate_rank(repo: dict) -> tuple[int, float]:
        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        return (-repo.get("stargazers_count", 0), -(pushed.timestamp()))

    fetch_candidates = []
    fetch_candidate_names = set()
    bucketed_candidates = {bucket: [] for bucket in DETAIL_FETCH_BUCKET_LIMITS}

    for repo in all_repos:
        bucket = candidate_bucket(repo)
        if bucket:
            bucketed_candidates[bucket].append(repo)

    for bucket, limit in DETAIL_FETCH_BUCKET_LIMITS.items():
        selected = sorted(bucketed_candidates[bucket], key=candidate_rank)[:limit]
        fetch_candidates.extend(selected)
        fetch_candidate_names.update(repo["full_name"] for repo in selected)
        print(f"  Reserved {len(selected)}/{limit} detail fetches for {bucket}")

    if len(fetch_candidates) < DETAIL_FETCH_LIMIT:
        remaining = [repo for repo in all_repos if repo["full_name"] not in fetch_candidate_names]
        for repo in sorted(remaining, key=candidate_rank)[:DETAIL_FETCH_LIMIT - len(fetch_candidates)]:
            fetch_candidates.append(repo)
            fetch_candidate_names.add(repo["full_name"])


    for i, repo in enumerate(fetch_candidates):
        owner, name = repo["full_name"].split("/", 1)

        commits, commits_capped, automated_share = get_commit_count_recent(
            owner, name, days=30, include_automation=True)
        commits_180d, commits_180d_capped = get_commit_count_recent(owner, name, days=180)
        contributor_metrics = get_contributor_metrics(owner, name)
        decision_signals = get_decision_signals(owner, name, now=now)

        repo_details[repo["full_name"]] = {
            "commits_30d_lower_bound": commits,
            "commits_30d_capped": commits_capped,
            "automated_commit_share": automated_share,
            "commits_180d_lower_bound": commits_180d,
            "commits_180d_capped": commits_180d_capped,
            **contributor_metrics,
            **decision_signals,
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
    # The ranked sections below are deliberately small editorial views.  Keep
    # a browser-facing record for every repository that passed the search
    # queries so discovery is not limited to those views.
    discovery = []

    current_stars = {}

    for repo in all_repos:
        full_name = repo["full_name"]
        stars = repo.get("stargazers_count", 0)
        current_stars[full_name] = stars

        topics = repo.get("topics", [])
        details = repo_details.get(full_name, {
            "commits_30d_lower_bound": None, "commits_30d_capped": False,
            "automated_commit_share": None,
            "commits_180d_lower_bound": None, "commits_180d_capped": False,
            "contributors_total_lower_bound": None, "contributors_capped": False,
            "top_contributor_share": None, "latest_release_age_days": None,
            "issue_responses_30d_lower_bound": None,
            "pull_request_responses_30d_lower_bound": None,
            "maintainer_responses_30d_lower_bound": None,
            "issues_closed_30d_lower_bound": None, "open_issue_growth_30d": None,
            "median_issue_response_hours": None, "release_cadence_days": None,
            "documentation_completeness": None, "test_ci_present": None,
            "response_activity_capped": False,
        })

        pushed = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        days_since_push = (now - pushed).days

        # Gem ranking treats unavailable detail neutrally for compatibility; the
        # readiness breakdown retains the distinction as missing data.
        gem = compute_gem_score(repo, details["commits_30d_lower_bound"] or 0,
                                details["contributors_total_lower_bound"] or 0,
                                details, return_details=True)
        gem_score = gem["gem_score"]
        readiness = compute_adoption_readiness(repo, details)
        classification = assign_category(topics, full_name, repo.get("description") or "",
                                         return_details=True)
        category = classification["category"]
        risk = classify_maintenance_risk(repo, details, category, now=now)
        metrics_estimated = full_name not in fetch_candidate_names
        maintainer_health = compute_maintainer_health(repo, details["commits_30d_lower_bound"],
                                                      details["contributors_total_lower_bound"])

        entry = {
            "name": full_name,
            "description": (repo.get("description") or "")[:200],
            "stars": stars,
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "language": repo.get("language") or "Unknown",
            # Keep every classification topic plus a useful display sample. The
            # frontend remains free to show fewer than this explanatory payload.
            "topics": list(dict.fromkeys(topics[:12] + [reason.split(":", 1)[1]
                           for reason in classification["category_reasons"]
                           if reason.startswith("topic:")])),
            "category": category,
            "secondary_categories": classification["secondary_categories"],
            "category_confidence": classification["category_confidence"],
            "category_reasons": classification["category_reasons"],
            "created_at": repo.get("created_at", ""),
            "pushed_at": repo.get("pushed_at", ""),
            "days_since_push": days_since_push,
            **details,
            **gem,
            "url": repo.get("html_url", ""),
            "owner_avatar": repo.get("owner", {}).get("avatar_url", ""),
            "archived": repo.get("archived", False),
            "license": (repo.get("license") or {}).get("spdx_id") if repo.get("license") else None,
            "metrics_estimated": metrics_estimated,
            **readiness,
            "maintainer_health": maintainer_health,
            "trend_reasons": [],
            **risk,
        }
        discovery.append(entry)

        # Classify
        if risk["at_risk"] and stars >= 200:
            entry["abandoned_flag"] = True  # legacy data/API compatibility
            abandoned.append(entry)

        if stars <= GEM_STAR_CEILING and gem_score >= 0.3:
            gems.append(entry)

        if stars >= MIN_STARS_FOR_TRENDING:
            trending.append(entry)

    # Compute history signals before truncating any candidate collection. This
    # ensures a fast-growing smaller repository can outrank a famous project.
    history = load_history()
    deltas = compute_star_deltas(current_stars, history, now=now)
    for entry in discovery:
        d = deltas.get(entry["name"], {})
        entry["history_coverage_days"] = d.get("history_coverage_days", 0)
        for window in TRENDING_WINDOWS:
            entry[f"stars_delta_{window}d"] = d.get(f"delta_{window}d")
            entry[f"stars_delta_{window}d_valid"] = d.get(f"delta_{window}d_valid", False)
        entry["trend_reasons"] = build_trend_reasons(entry)

    trending_rankings = {
        f"{window}d": rank_trending(trending, window)
        for window in TRENDING_WINDOWS
    }

    # Sort non-trending collections and retain a compatibility union of every
    # window's results rather than a total-star-prefiltered candidate list.
    gems.sort(key=lambda r: r["gem_score"], reverse=True)
    abandoned.sort(key=lambda r: (-r["maintenance_risk_score"],
                                  -r["risk_confidence"], -r["stars"], r["name"].lower()))
    trending_by_name = {}
    for window in TRENDING_WINDOWS:
        for entry in trending_rankings[f"{window}d"]:
            trending_by_name.setdefault(entry["name"], entry)
    trending = list(trending_by_name.values())
    gems = gems[:30]
    abandoned = abandoned[:20]

    # -----------------------------------------------------------------------
    # Step 4: Compute star deltas from history
    # -----------------------------------------------------------------------
    print("\n[4/5] Computing star deltas...")
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
            "abandoned_candidates_evaluated": len(abandoned_candidates_seen),
        },
        "trending": trending,
        "trending_rankings": trending_rankings,
        "gems": gems,
        "abandoned": abandoned,
        "discovery": discovery,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Done. {len(trending)} trending, {len(gems)} gems, {len(abandoned)} abandoned.")
    print(f"  Data written to {DATA_FILE}")
    print(f"  Total API requests: {_request_count}")


if __name__ == "__main__":
    collect()
