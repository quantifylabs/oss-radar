# Recommendation evaluation process

Run this review monthly and before merging any scoring or threshold change.

1. Freeze the collector revision and data timestamp. Randomly sample at least 20 entries from each of Trending, Underrated Gems, and Stale / At Risk. Record the random seed and repository URLs in a dated copy of `docs/evaluations/template.csv`.
2. Have a reviewer inspect repository activity and documentation without looking at the score. Judge whether each list assignment is useful (`1`) or not (`0`), add a short evidence note, and mark uncertain cases for a second reviewer.
3. Report precision (`useful / judged`) with numerator and denominator for every view and overall. Keep disagreements visible and resolve them with a documented final judgment; do not silently remove failures.
4. Run the current and proposed scoring implementations against `tests/fixtures/scoring_benchmark.json`. Record each changed label/rank and explain why it is intended. Fixture changes require evidence in the pull request and reviewer approval; never rewrite fixtures merely to make a new algorithm pass.
5. Accept a change only when no protected fixture regresses without an explicit rationale and sampled precision does not materially decline. Store the completed CSV and comparison summary under `docs/evaluations/YYYY-MM/` so results can be compared over time.

The benchmark is intentionally small and fixed; production sampling detects distribution drift while the fixture catches deterministic scoring regressions.
