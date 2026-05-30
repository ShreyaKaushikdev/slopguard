# SlopGuard PR Check — GitHub Action

Score PR descriptions and code comments for human oversight. Posts inline annotations on low-quality content and sets a check status on every PR.

## Usage

Add this to your repo's `.github/workflows/slopguard.yml`:

```yaml
name: SlopGuard PR Check
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  slopguard:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      checks: write
    steps:
      - uses: slopguard/pr-check@v1
        with:
          min_score: 60
          fail_on: description_slop
          annotate_diff: true
```

## Inputs

| Input | Description | Default |
| --- | --- | --- |
| `api_url` | SlopGuard API URL | `https://api.slopguard.dev` |
| `min_score` | Minimum oversight score to pass (0-100) | `60` |
| `fail_on` | Conditions that fail the check (comma-separated) | `description_slop` |
| `annotate_diff` | Post inline review comments on low-quality sentences | `true` |
| `comment_summary` | Post a summary review comment on the PR | `true` |
| `domain` | Domain adapter for scoring | `code_review` |
| `github_token` | GitHub token (auto-provided) | `${{ github.token }}` |

### `fail_on` Options

- `description_slop` — Fail if PR description score is below `min_score`
- `rubber_stamp` — Fail if reviewer impact is low (approving without review)
- `low_comment_intelligence` — Fail if code comments just restate the code

## Outputs

| Output | Description |
| --- | --- |
| `score` | The overall oversight score (0-100) |
| `oversight` | Oversight classification (`high`, `mixed`, `low`) |
| `flagged_claims` | JSON array of flagged reasoning claims |

## What It Does

1. **Fetches PR metadata** — title, body, and diff from the GitHub API
2. **Scores with SlopGuard** — sends to the detection API with the `code_review` adapter
3. **Posts inline annotations** — review comments on sentences with unfalsifiable reasoning (file-aware when diff is available)
4. **Posts a summary comment** — a top-level PR comment with score, reasoning analysis, and suggestions
5. **Creates a check run** — pass/fail status visible in the PR timeline
6. **Summarizes results** — specificity score, flagged claims, strong claims in the check output

## Example PR Annotations

When a PR description has low-quality reasoning, SlopGuard posts comments like:

> **SlopGuard: Unfalsifiable Reasoning**
>
> Add measurement — "it aligns better with our architectural principles"? Under what conditions?
>
> *Specificity: 0.12*

For high-quality reasoning:

> **SlopGuard: Specific Reasoning** ✅
>
> Profiling showed auth middleware adding 340ms to every request.
>
> *Specificity: 0.94*

## Self-Hosting the API

If you're running your own SlopGuard API:

```yaml
- uses: slopguard/pr-check@v1
  with:
    api_url: https://your-slopguard-api.example.com
    min_score: 50
    fail_on: description_slop,rubber_stamp
```

## License

MIT
