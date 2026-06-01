# slopguard

SlopGuard CLI — Score content for human oversight. Detect low-effort AI slop in PRs, docs, reviews, and more.

## Installation

### Python (recommended)
```bash
pip install slopguard
```

### Node.js (wrapper)
```bash
npm install -g slopguard
# or use npx
npx slopguard score "your text here"
```

## Usage

### Score text
```bash
slopguard score "Updated files and improved the implementation."
slopguard score "Updated files" --domain code_review
```

### Score from file
```bash
slopguard score --file README.md --domain docs
```

### Score a GitHub PR
```bash
slopguard score --pr https://github.com/org/repo/pull/123
```

### Get improvement suggestions
```bash
slopguard improve "Updated files because it was slow."
```

### Batch scoring
```bash
slopguard batch ./samples.json
```

### Evaluate labeled dataset
```bash
slopguard evaluate ./labeled.json
```

### HC3 Benchmark
```bash
slopguard hc3              # Full evaluation
slopguard hc3 --fast       # Quick subset
slopguard hc3 --domain reddit  # Single domain
```

### Use remote API
```bash
slopguard score "text" --api-url https://api.slopguard.dev
```

## Output

```json
{
  "score": 42,
  "oversight": "low",
  "signals": [
    {"name": "information_density", "score": 0.35, "label": "sparse", "reason": "..."},
    {"name": "why_vs_what", "score": 0.12, "label": "what_heavy", "reason": "..."},
    ...
  ]
}
```

## Domains

| Domain | Use Case |
|---|---|
| `code_review` | PR descriptions, code comments |
| `docs` | Technical documentation |
| `hiring` | Resumes, cover letters |
| `communications` | Slack messages, emails |
| `content` | Blog posts, articles |
| `academia` | Research papers, citations |
| `marketplace` | Product reviews |
| `social_news` | Reddit, Twitter, news |

## API

Start the API server:
```bash
cd apps/api
uvicorn slopguard.main:app --reload
```

Then use:
```bash
curl -X POST http://localhost:8000/score/text \
  -H "Content-Type: application/json" \
  -d '{"text": "your text", "domain": "code_review"}'
```

## License

MIT
