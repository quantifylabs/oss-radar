# Privacy-conscious product analytics

The shipped configuration is **no analytics**: the `oss-radar-analytics-endpoint` meta value in `site/index.html` is empty. The dashboard makes no analytics request in that state and remains fully functional on GitHub Pages.

## Success events

| Event | Meaningful outcome |
|---|---|
| `repository_opened` | A user chose to open a repository. The repository is deliberately not identified. |
| `feed_subscribed` | A user opened the RSS feed. |
| `filters_applied` | A user committed a changed discovery control. Values are not sent. |
| `comparison_created` | A comparison first reached two repositories. Contents are not sent. |
| `share_url_copied` | The shareable discovery URL was copied. The URL is not sent. |
| `label_reported` | A structured correction form was opened. Its contents remain in GitHub Issues. |

## Optional self-hosting

Set the meta value to an HTTPS endpoint that accepts `POST` requests containing only `{"event":"<allowlisted-name>"}`. The receiver should reject other keys and names, increment a daily aggregate counter, discard request logs/IP addresses, and retain daily totals only as long as needed (90 days is a reasonable default). Do not add cookies, fingerprinting, referrers, repository identifiers, query strings, or filter values.

Before enabling it, update `site/privacy.html` with the endpoint operator, retention period, and contact. Confirm the endpoint's CORS/content-type behavior with both `sendBeacon` and the fetch fallback. A simple self-hosted serverless counter can remain zero-cost, but the default no-analytics configuration is preferred when those privacy guarantees cannot be maintained.
