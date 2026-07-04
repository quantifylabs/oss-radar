# OSS Radar — AI Open-Source GitHub Repository Tracker

Track trending AI open-source GitHub repositories, discover underrated gems, compare adoption risk, and spot abandoned repos.

**Zero cost.** Runs on GitHub Actions (free) + GitHub Pages (free). No servers, no databases, no cloud bills.

**Live at:** [radar.aegismemory.com](https://radar.aegismemory.com)

## What it does

- **Trending** — Top AI repos by star growth (3-day / 7-day / 30-day windows)
- **Underrated Gems** — High-quality repos under 500 stars that most people haven't found yet
- **Abandoned Detector** — Popular repos with stale pushes or weak maintenance signals (the "hot but dead" trap)
- **Category filtering** — Agent frameworks, model serving, RAG, fine-tuning, MCP, dev tools, evals, MLOps
- **Adoption signals** — Adoption readiness, maintainer health, and deterministic trend explanations for safer tool selection
- **Auto-updated** — GitHub Actions cron runs every 6 hours

## Scoring algorithms

### The Gem Score algorithm

Each repo gets a weighted quality score (0-100%):

| Signal | Weight | What it measures |
|--------|--------|-----------------|
| Commit velocity | 30% | Commits per week over last 30 days |
| Issue engagement | 20% | Open issues relative to stars (community interest) |
| Star acceleration | 15% | Stars gained per day of existence |
| Contributor diversity | 15% | Unique contributors (bus-factor proxy) |
| Docs quality | 10% | Description length + topic tag coverage |
| Push recency | 10% | How recently the repo was updated |

Repos with < 500 stars and gem score ≥ 30% make the "Underrated Gems" list.

### Adoption readiness and maintainer health

The collector also emits deterministic adoption-readiness and maintainer-health signals. These combine push recency, recent commits, contributor diversity, issue pressure, fork signal, topic coverage, license presence, and archived status into simple labels such as `safe`, `watch`, and `risky`.

---

## Setup — Step by step

### Step 1: Create the GitHub repo

```bash
# Clone this project
git clone <this-repo-url> oss-radar
cd oss-radar
```

Or create a new repo on GitHub named `oss-radar` and push these files to it.

### Step 2: Create a GitHub Personal Access Token (PAT)

The collector needs a token to avoid API rate limits (unauthenticated = 60 req/hr, authenticated = 5,000 req/hr).

1. Go to https://github.com/settings/tokens?type=beta
2. Click **"Generate new token"** (Fine-grained token)
3. Name it `oss-radar-collector`
4. Set expiration to 90 days (you'll rotate it quarterly)
5. Under **Repository access** → select "Public Repositories (read-only)"
6. No additional permissions needed — read-only public access is enough
7. Click **Generate token**
8. **Copy the token** (you won't see it again)

### Step 3: Add the token as a GitHub Actions secret

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Name: `GH_PAT`
4. Value: paste the token from Step 2
5. Click **Add secret**

### Step 4: Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Under **Source**, select **"GitHub Actions"**
3. Save

### Step 5: Run the collector for the first time

You have two options:

**Option A — Run locally (recommended for first time):**

```bash
# Install dependency
pip install requests

# Set your token
export GITHUB_TOKEN="ghp_your_token_here"

# Run the collector
python collector/collect.py

# Check the output
cat site/data.json | head -20
```

**Option B — Trigger via GitHub Actions:**

1. Go to your repo → **Actions** tab
2. Click **"Collect & Deploy"** workflow on the left
3. Click **"Run workflow"** → **"Run workflow"** (the green button)
4. Wait ~5 minutes for it to complete

### Step 6: Set up the custom domain (optional)

If you want `radar.aegismemory.com`:

1. Go to your DNS provider (wherever aegismemory.com is registered)
2. Add a **CNAME record**:
   - Name: `radar`
   - Value: `quantifylabs.github.io` (or your GitHub username + `.github.io`)
   - TTL: 3600
3. Go to your repo → **Settings** → **Pages**
4. Under **Custom domain**, enter `radar.aegismemory.com`
5. Check **"Enforce HTTPS"**
6. Wait 5-10 minutes for DNS propagation + SSL certificate

If you don't want a custom domain, delete the `site/CNAME` file. Your site will be at `https://<username>.github.io/oss-radar/`.

### Step 7: Verify automation

After the first successful run, the cron job will run automatically every 6 hours (00:00, 06:00, 12:00, 18:00 UTC). Check:

1. **Actions tab** → you should see scheduled runs
2. **site/data.json** → should have real repo data
3. **Your URL** → the dashboard should render with repos

---

## Project structure

```
oss-radar/
├── .github/
│   └── workflows/
│       └── collect.yml      # GitHub Actions: cron + deploy
├── collector/
│   ├── collect.py           # Main collection script
│   ├── render_pages.py      # Static pages, sitemap, robots, feeds
│   ├── validate_site.py     # Pre-deploy site/data checks
│   └── requirements.txt     # Just: requests
├── site/
│   ├── index.html           # Frontend dashboard
│   ├── data.json            # Generated data (auto-updated)
│   ├── history.json         # Star snapshots (for computing deltas)
│   ├── robots.txt           # Crawler policy
│   ├── sitemap.xml          # Generated sitemap
│   ├── feed.xml             # Generated RSS feed
│   └── CNAME                # Custom domain config
├── .gitignore
└── README.md
```

## Architecture

```
GitHub Actions cron (every 6h, free)
        │
        ▼
collector/collect.py
        │
        ├── GitHub Search API → find AI repos by topic
        ├── GitHub REST API  → fetch commits, contributors
        ├── Gem Score engine  → weighted quality scoring
        ├── Adoption signals  → readiness + maintainer health
        ├── Static page render → sitemap, feeds, crawlable category pages
        └── Star delta calc   → compare with history.json
        │
        ▼
site/data.json (committed to repo)
        │
        ▼
GitHub Pages (free static hosting)
        │
        ▼
radar.aegismemory.com
```

**Total monthly cost: ₹0**

- GitHub Actions: ~90 min/month (free tier = 2,000 min)
- GitHub Pages: free for public repos
- GitHub API: ~1,200 req/day (free tier = 5,000/hr)
- Domain: already owned

## Customizing

### Add more topics to scan

Edit `SEARCH_TOPICS` in `collector/collect.py`:

```python
SEARCH_TOPICS = [
    "llm", "ai-agent", ...
    "your-new-topic",  # add here
]
```

### Change the gem threshold

Edit `GEM_STAR_CEILING` in `collector/collect.py`:

```python
GEM_STAR_CEILING = 500   # max stars to qualify as "underrated"
```

### Change scan frequency

Edit `.github/workflows/collect.yml`:

```yaml
schedule:
  - cron: "0 */6 * * *"   # every 6 hours
  # - cron: "0 */12 * * *" # every 12 hours
  # - cron: "0 0 * * *"    # once daily at midnight
```

## Tech stack

- **Python 3.12** + `requests` — data collection
- **GitHub REST API** — repo discovery and metadata
- **Static HTML/CSS/JS** — no framework, no build step
- **GitHub Actions** — cron scheduler
- **GitHub Pages** — hosting

## License

MIT — Quantify Labs Ltd

---

Built by [Arulnidhi Karunanidhi](https://arulnidhii.github.io) · [Quantify Labs](https://github.com/quantifylabs)
