# OSS Radar implementation tasks

This backlog converts the GitHub Actions, SEO, product, and competitive-analysis findings into implementable tasks.

## P0 — Reliability and correctness

### 1. Harden GitHub Pages deployment

**Goal:** Reduce failed deployments and make future failures easier to diagnose.

**Implementation notes:**

- Add top-level workflow `concurrency` to `.github/workflows/collect.yml` for Pages deployments, using a stable group such as `pages-${{ github.ref }}` and `cancel-in-progress: false`.
- Upgrade GitHub Actions to the current Node-compatible major versions.
- Add a diagnostic step before Pages deployment that prints the `site/` artifact contents and key file sizes.
- Consider splitting collection and deployment into clearly named jobs: collect, commit data, upload artifact, deploy.

**Acceptance criteria:**

- Concurrent scheduled runs do not interrupt each other during Pages deployment.
- Deploy logs show enough artifact information to distinguish bad build output from GitHub Pages service failures.
- The workflow has no Node runtime deprecation warnings.

### 2. Escape untrusted GitHub metadata in the frontend

**Goal:** Prevent GitHub repository metadata from injecting HTML into the dashboard.

**Implementation notes:**

- Add an `escapeHtml(value)` helper in `site/index.html`.
- Escape repo names, descriptions, languages, categories, topic labels, and any other text sourced from `site/data.json`.
- Validate external URLs before rendering links or image sources. Accept expected GitHub and GitHub avatar URL prefixes only.
- Prefer DOM APIs over large `innerHTML` templates if the card renderer grows further.

**Acceptance criteria:**

- Repo descriptions and topics containing HTML-like characters render as text.
- Links and avatar image URLs are validated before use.
- The dashboard still renders the existing data without visual regressions.

### 3. Fix abandoned repository discovery

**Goal:** Make the advertised abandoned-repo detector produce meaningful results.

**Implementation notes:**

- Keep the current recent-push search path for active and trending repos.
- Add a separate abandoned-candidate search path without `pushed:>{thirty_days_ago}` or with an explicit stale-push query.
- Use category/topic filters and a minimum star threshold to keep abandoned candidates relevant.
- Enrich abandoned candidates with commit and contributor data when API budget allows.

**Acceptance criteria:**

- The abandoned list can include repositories that have not been pushed in more than `ABANDONED_DAYS`.
- The output stats include how many abandoned candidates were evaluated.
- The frontend abandoned tab is non-empty when matching stale repositories exist.

### 4. Prioritize collector enrichment by product relevance

**Goal:** Avoid showing default zero/one metrics for the most visible dashboard entries.

**Implementation notes:**

- Replace ascending-star-only enrichment with a relevance-ranked candidate list.
- Include likely gems, likely trending repos, and likely abandoned repos in the enrichment pool.
- Deduplicate candidates by `full_name` before applying `DETAIL_FETCH_LIMIT`.
- Mark unenriched entries with `metrics_estimated: true` so the UI can avoid overclaiming precision.

**Acceptance criteria:**

- Top trending, gem, and abandoned entries receive commit and contributor enrichment whenever budget permits.
- Unenriched entries are explicitly marked in `site/data.json`.
- The UI can distinguish exact metrics from fallback values.

## P1 — Search visibility and crawlability

### 5. Add baseline SEO metadata and crawler files

**Goal:** Improve discoverability for brand and category queries.

**Implementation notes:**

- Add `site/robots.txt` that allows crawling and references `https://radar.aegismemory.com/sitemap.xml`.
- Add `site/sitemap.xml` with the homepage and future static category pages.
- Add canonical URL, `og:url`, `og:image`, Twitter card metadata, and JSON-LD structured data to `site/index.html`.
- Add a crawlable description of OSS Radar near the homepage hero.

**Acceptance criteria:**

- `robots.txt` and `sitemap.xml` are present in the Pages artifact.
- The homepage has canonical, Open Graph, Twitter card, and JSON-LD metadata.
- The visible copy clearly says OSS Radar tracks AI open-source GitHub repositories.

### 6. Generate static category and list pages

**Goal:** Create indexable long-tail pages instead of relying only on JavaScript-rendered JSON.

**Implementation notes:**

- Add a static page generator that reads `site/data.json`.
- Generate pages such as:
  - `site/trending/index.html`
  - `site/gems/index.html`
  - `site/abandoned/index.html`
  - `site/categories/mcp/index.html`
  - `site/categories/rag-and-search/index.html`
- Include crawlable repo names, descriptions, topics, star counts, and GitHub links.
- Add generated pages to `sitemap.xml`.

**Acceptance criteria:**

- Generated pages are linked from the homepage.
- Generated pages render useful repo content without JavaScript.
- Generated URLs are included in the sitemap.

### 7. Strengthen brand positioning for ambiguous search terms

**Goal:** Help search engines and users understand that OSS Radar is an AI open-source repository tracker.

**Implementation notes:**

- Use consistent wording across README, homepage title, meta description, hero copy, and footer.
- Add FAQ copy answering:
  - What is OSS Radar?
  - How is OSS Radar different from GitHub Trending?
  - How does the gem score work?
- Mention the custom domain prominently in README.

**Acceptance criteria:**

- The homepage and README use the phrase “AI open-source GitHub repository tracker” or equivalent.
- FAQ content is crawlable in the initial HTML.
- Brand and product-purpose copy is consistent across repo and site.

## P2 — Product differentiation

### 8. Add an adoption readiness score

**Goal:** Move beyond popularity and help users decide whether a project is safe to adopt.

**Implementation notes:**

- Add `compute_adoption_score(repo, commits_30d, contributors)` to the collector.
- Consider release recency, push recency, contributor diversity, issue ratio, license presence, stars/forks ratio, topic coverage, and archived status.
- Output `adoption_score` and `adoption_label` values such as `safe`, `watch`, and `risky`.
- Display the score and label on repo cards.

**Acceptance criteria:**

- Each repo entry has adoption score fields.
- The score is documented in README.
- Users can visually distinguish safe, watch, and risky projects.

### 9. Add repository comparison

**Goal:** Let users compare candidate tools directly inside OSS Radar.

**Implementation notes:**

- Add a compare mode that lets users select two to four repos.
- Compare stars, forks, star deltas, commits in 30 days, contributors, open issues, category, topics, gem score, and adoption score.
- Make comparison URLs shareable.

**Acceptance criteria:**

- Users can select multiple repos and see a comparison table.
- The comparison works on mobile and desktop.
- The selected comparison state can be shared with a URL.

### 10. Add “why this is trending” explanations

**Goal:** Make trending lists more actionable and less opaque.

**Implementation notes:**

- Generate short reason strings from available metrics, such as star delta, commit velocity, contributor count, or category momentum.
- Add a `trend_reasons` array to each relevant repo entry.
- Display one or two concise reasons on repo cards.

**Acceptance criteria:**

- Trending repos include readable reasons in `site/data.json`.
- The UI explains why a repo appears in the trending list.
- Reasons are deterministic and do not require external AI calls.

### 11. Add alternatives pages for popular AI tools

**Goal:** Capture high-intent searches such as “open-source alternatives to LangChain”.

**Implementation notes:**

- Group repos by shared category and overlapping topics.
- Generate alternatives pages for high-profile repos in each category.
- Include comparison tables and links back to category pages.
- Add alternatives URLs to the sitemap.

**Acceptance criteria:**

- At least five alternatives pages are generated from current data.
- Each page has crawlable headings, descriptions, and comparison rows.
- The sitemap includes alternatives pages.

### 12. Add RSS feeds and category alerts

**Goal:** Give users a low-friction way to follow updates.

**Implementation notes:**

- Generate `site/feed.xml`, `site/feeds/trending.xml`, `site/feeds/gems.xml`, and category-specific feeds.
- Include repo name, description, category, stars, deltas, GitHub URL, and scan timestamp.
- Link the main feed from the homepage with `<link rel="alternate" type="application/rss+xml">`.

**Acceptance criteria:**

- RSS feeds validate with a standard feed validator.
- Feed links are discoverable from the homepage.
- README documents available feeds.

### 13. Add maintainer health signals

**Goal:** Highlight adoption risk before users commit to a project.

**Implementation notes:**

- Enrich selected repos with archived status, license, recent release data, issue pressure, and open pull request count where API limits permit.
- Compute `maintainer_health` from push recency, release recency, contributors, issue pressure, and archived status.
- Add filters for healthy, watch, and risky repos.

**Acceptance criteria:**

- Repo entries include maintainer health fields.
- The UI displays health badges.
- Users can filter by health status.

## P3 — Measurement and operations

### 14. Add SEO and indexing checks to the workflow

**Goal:** Prevent regressions in crawlability.

**Implementation notes:**

- Add a lightweight script that checks for `robots.txt`, `sitemap.xml`, canonical metadata, and required Open Graph tags.
- Run the check in CI before deployment.
- Fail the workflow when critical SEO assets are missing.

**Acceptance criteria:**

- CI fails if `robots.txt` or `sitemap.xml` is missing.
- CI fails if the homepage lacks canonical metadata.
- The check is documented in README or contributor notes.

### 15. Add data quality checks

**Goal:** Prevent empty or misleading dashboards from being deployed.

**Implementation notes:**

- Add a validation script for `site/data.json`.
- Check required top-level keys, non-empty list expectations, timestamp validity, and required fields per repo entry.
- Warn or fail when metrics are suspiciously empty after a successful collector run.

**Acceptance criteria:**

- The workflow validates generated JSON before uploading the Pages artifact.
- Required fields are enforced.
- Empty dashboard states are caught before deployment unless explicitly allowed.
