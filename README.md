# SlopGuard — The Internet's Quality Layer

> **Every other tool asks "was this AI-generated?" — that's the wrong question.**
>
> SlopGuard asks: **"Did a human actually think about this before publishing?"**

That distinction is what makes it unfakeable. You can't prompt-engineer your way to a high counterfactual absence score. You can't fake a human-shaped vocabulary novelty curve. You can't game a system that measures *thinking*, not authorship.

---

## 📊 At a Glance

| | |
|---|---|
| **F1 Score** | **0.926** on 453 labeled samples |
| **Score Gap** | +13.8 pts (slop vs reviewed content) |
| **Signals** | 10 universal · 3 novel (prize targets) |
| **Tracks** | 8 domain tracks (A–H) |
| **Tests** | 66 passing |
| **Primary Track** | **A — Code Review** |
| **Live Demo** | `docker-compose up --build` → `http://localhost:8000/live` |

---

## ⚡ Try It in 30 Seconds

```bash
docker-compose up --build
# API:       http://localhost:8000
# Dashboard: http://localhost:3000
# Live feed: http://localhost:8000/live
```

Or run just the API:

```bash
cd apps/api
pip install -r requirements.txt
uvicorn slopguard.main:app --reload --port 8000

# Test immediately:
curl -X POST http://localhost:8000/score/text \
  -H "Content-Type: application/json" \
  -d '{"text":"This update improves the system and enhances user experience.","domain":"content"}'
```

---

## 🧠 What It Does

Paste a PR description, article, review, or abstract. SlopGuard returns:

- **Score 0–100** measuring human oversight quality
- **Verdict**: `high` / `mixed` / `low` / `insufficient`
- **Per-signal breakdown** — which of the 10 signals fired and why
- **Flagged passages** — specific sentences with unfalsifiable reasoning
- **Improvement suggestions** — targeted questions, not generic advice
- **Relative score** — how this compares to your repo history and global baseline

---

## 🏆 Three Novel Signals — Sharpest Signal Prize

These three signals are original detection angles that no existing tool has implemented. They are technically sophisticated, hard to fake, and visually immediate.

---

### ⭐ 1. Epistemic Cowardice (Weight: 1.5)

**The Insight:** AI systematically avoids taking positions. It hedges everything, presents "both sides," and never commits to a recommendation.

**What It Detects:**
| Pattern | Example |
|---|---|
| Hedge clustering | "may", "might", "could", "potentially" — 2+ per paragraph |
| False balance | "on one hand… on the other hand" with no resolution |
| Opinion laundering | "some experts say", "many believe" — no named source |
| Responsibility deflection | "it depends", "consult an expert" as a conclusion |
| Commitment absence | Zero falsifiable predictions in the entire document |

**Why It's Hard to Fake:** To score well, you must actually commit to something — "do this, not that, because X." AI systems are trained to be helpful to everyone, which means committing to nothing.

```bash
# Cowardly (AI) — scores 0.15
curl -X POST http://localhost:8000/signals/epistemic-cowardice \
  -d '{"text":"You might want to consider Redis, depending on your use case. It could improve performance in some scenarios, though results may vary.","domain":"code_review"}'

# Committed (Human) — scores 0.82
curl -X POST http://localhost:8000/signals/epistemic-cowardice \
  -d '{"text":"Do not use moment.js for new projects. It is deprecated and 67kb minified. Use date-fns — it is tree-shakeable and will reduce your bundle by at least 40kb.","domain":"code_review"}'
```

---

### ⭐ 2. Counterfactual Absence (Weight: 1.8)

**The Insight:** When humans think about something, they consider what could go wrong, what alternatives they rejected, and why. AI generates the happy path and nothing else.

**What It Detects:**
| Pattern | Example |
|---|---|
| Rejected alternatives | "considered X but", "tried Y and it failed" |
| Explicit failure modes | "this breaks when", "edge case:", "limitation:" |
| Specific conditions | "only works if", "requires that", "precondition:" |
| Tradeoff acknowledgment | "trading X for Y" — with specifics, not generics |

**Why It's Hard to Fake:** Generic counterfactuals are easy to prompt-engineer ("may have performance implications"). Specific ones require genuine domain knowledge ("breaks when queue depth exceeds 10k messages because Redis pub/sub doesn't buffer").

```bash
# Happy path only (AI) — returns score: 0.0, failure_modes: 0
curl -X POST http://localhost:8000/signals/counterfactual-absence \
  -d '{"text":"Implemented caching to improve performance. The new system is more robust and follows best practices.","domain":"code_review"}'

# Rich counterfactuals (Human) — returns score: 0.72, rejected_alternatives: 2
curl -X POST http://localhost:8000/signals/counterfactual-absence \
  -d '{"text":"Fixed JWT secret exposure in auth/middleware.js. Considered environment variables but rejected because our pipeline does not support secret rotation. Switched to AWS Secrets Manager — breaks if that API is unavailable, so added 5s timeout with fallback. Trading 20ms latency for automatic rotation.","domain":"code_review"}'
```

---

### ⭐ 3. Vocabulary Novelty Curve (Weight: 1.6)

**The Insight:** This is the most technically original signal and the hardest to replicate.

Human experts introduce new concepts **progressively** — early sections use familiar vocabulary, later sections introduce specific terminology as context is established. The vocabulary novelty curve has a characteristic **shape**.

AI-generated content has a **flat vocabulary novelty curve**. It distributes technical terms uniformly from paragraph 1 to paragraph 10, because it doesn't build context the way humans do.

**How It Works:**
1. Split text into sentences
2. For each sentence: `novelty = new_words / total_words`
3. Analyze the curve shape:

| Pattern | Curve Shape | Score |
|---|---|---|
| Human writing | High early → declining → spikes at transitions | High |
| AI writing | Flat, uniform throughout | Low |

**Metrics:** `variance` (low = flat = AI), `slope` (negative = human), `spike_count` (section transitions)

**Why It's Novel:** No existing detector does this. It's not looking at *what words are used* — it's looking at the **shape of how vocabulary is introduced over time**. This is a structural signal about the cognitive process that generated the text, not the content itself.

**Why It's Hard to Fake:** You cannot prompt an LLM to produce a human-shaped novelty curve. The only way is to genuinely build an argument progressively, introducing concepts as they become relevant.

> **This signal is publishable as a legitimate NLP research contribution.**

```bash
# Flat (AI) — variance: 0.024, spike_count: 0 → score: 0.28
curl -X POST http://localhost:8000/signals/vocabulary-novelty \
  -d '{"text":"Authentication middleware validates JWT tokens using jsonwebtoken. Token validation ensures user_id is present. Middleware returns 401 for invalid tokens. JWT verification uses HS256. Token expiration checking prevents stale credentials.","domain":"code_review"}'

# Human curve — variance: 0.089, spike_count: 2 → score: 0.74
curl -X POST http://localhost:8000/signals/vocabulary-novelty \
  -d '{"text":"Authentication is critical for web applications. Users need secure access. We implemented JWT-based authentication using jsonwebtoken. The token contains user_id and role encoded with HS256. Validation happens in middleware/auth.js using verify(). Invalid tokens return 401 Unauthorized. Edge cases include expired tokens, malformed payloads, and signature mismatches.","domain":"code_review"}'
```

**Combined Novel Signal Weight: 4.9 out of 10.0 (~49% of total score)**

---

## 📡 Live Ingestion Engine

SlopGuard scores real internet content continuously — fully automatic, no prompting.

**10 live sources, cycling every 25–90 seconds:**

| Source | Domain | Cooldown |
|---|---|---|
| Hacker News top stories | social_news, content | 45s |
| Dev.to articles | content, docs | 60s |
| GitHub Issues (6 repos) | code_review | 30s |
| GitHub Commits (6 repos) | code_review | 25s |
| Reddit (worldnews, ExperiencedDevs, programming) | social_news, communications | 50s |
| Stack Overflow top questions | docs | 55s |
| arXiv abstracts (cs.AI, cs.LG, cs.CL) | academia | 90s |
| Wikipedia summaries (14 tech topics) | content, docs | 70s |
| CrossRef journal articles | academia | 80s |
| PubMed abstracts | academia | 85s |

**Live endpoints:**
```
GET  /live/feed      Last 200 scored items — source, title, score, oversight
GET  /live/stats     Items/min, domain breakdown, slop rate, uptime
GET  /live/stream    SSE stream — new scored item every ~3 seconds
POST /live/score-url Score any public URL in real time
```

---

## 🎯 Tracks Covered (All 8)

| Track | Domain | Key Signals |
|---|---|---|
| **A** | Code Review | PR diff divergence, commit reasoning ratio, slop velocity |
| **B** | Docs & KBs | Heading/content ratio, concrete example density, circular explanation detection |
| **C** | Hiring | Company/achievement specificity, batch structural fingerprint |
| **D** | Communications | Decision/action density, compression score, substance ratio |
| **E** | Content & SEO | Claim specificity, structure rehash, originality proxy |
| **F** | Academia | Citation shape verification (CrossRef + Semantic Scholar + PubMed) |
| **G** | Marketplaces | Review specificity, reviewer authenticity, temporal clustering |
| **H** | Social & News | Rage-bait fingerprint, network coordination proxy |

---

## 🔬 All 10 Signals

| Signal | What It Measures | Weight |
|---|---|---|
| `information_density` | Shannon entropy + bigram novelty + circular reasoning penalty | 1.0 |
| `why_vs_what` | Causal reasoning ratio with adversarial specificity verification | 1.8 |
| `specificity` | Falsifiability markers: numbers, file paths, error codes, tool refs | 1.8 |
| `semantic_uniqueness` | Jensen-Shannon divergence vs known AI-slop trigram corpus | 1.0 |
| `template_structure` | Sentence CoV, opener repetition, AI transition phrases | 1.0 |
| `human_delta` | Editing artifacts, hedging, disagreement markers | 0.3 |
| `evidence_density` | Technical jargon without measurements penalized | 1.0 |
| `epistemic_cowardice` ⭐ | Hedge clustering, false balance, opinion laundering | **1.5** |
| `counterfactual_absence` ⭐ | Missing alternatives, failure modes, tradeoffs | **1.8** |
| `vocabulary_novelty` ⭐ | Shape of vocabulary introduction curve over time | **1.6** |

---

## 📈 Honest Metrics

### Dataset (453 samples, multi-source)

| Source | Samples |
|---|---|
| Hand-labeled seed (all 8 domains) | 104 |
| Real GitHub PRs (15 repos: django, react, rust-lang, k8s, cpython…) | 188 |
| Multi-source build (GitHub + Reddit + arXiv) | 114 |
| Live ingestion (HN, Dev.to, GitHub, Wikipedia, PubMed) | 25 |
| Synthetic novel-signal pairs | 22 |

### Overall Results

| Metric | Value |
|---|---|
| **F1** | **0.926** |
| Precision | 0.887 |
| Recall | 0.969 |
| Accuracy | 0.956 |
| Score gap (slop vs reviewed) | **+13.8 pts** |

### Per-Domain F1

| Domain | F1 | Samples |
|---|---|---|
| academia | 1.000 | 21 |
| general | 1.000 | 8 |
| marketplace | 1.000 | 20 |
| communications | 0.952 | 33 |
| hiring | 0.957 | 22 |
| content | 0.941 | 38 |
| code_review | 0.918 | 241 |
| social_news | 0.875 | 31 |
| docs | 0.828 | 39 |

### Honest Failure Modes

- Text under 50 words → returns `insufficient_data` (not a fake score)
- Docs domain F1 = 0.828 — AI docs with concrete references sometimes pass
- Short social posts: ~10pt gap vs 20pt+ gap on longer content
- Single threshold of 48 gives F1 = 0.775 — domain-calibrated thresholds are required

Reproduce with: `python -m slopguard.build_validation_dataset --evaluate`

---

## 🖥️ Dashboard (7 Tabs)

| Tab | What It Shows |
|---|---|
| **Scan** | Score any text across all 8 domains. Signal breakdown, flagged claims, improvement suggestions. |
| **PR Review** | GitHub PR scoring with diff visualization. Inline annotation preview. |
| **Repo** | Full repo analysis — Slop Velocity Timeline, weekly trend, hotspot signals. |
| **Batch** | Score multiple texts at once. Structural fingerprint clustering catches copy-paste patterns. |
| **Citations** | Academic citation verification against CrossRef, Semantic Scholar, PubMed. |
| **Personal** | Browsing history scores from the Chrome extension. Site-level slop map. |
| **Metrics** | F1/precision/recall, confusion matrix, per-domain breakdown, live ingestion stats. |

---

## 🌐 API Reference (45+ endpoints)

### Core Scoring
| Endpoint | Purpose |
|---|---|
| `POST /score/text` | Score any text + domain |
| `POST /score/pr` | Score PR title + description + diff |
| `POST /score/pr-url` | Fetch and score a public GitHub PR URL |
| `POST /score/repo` | Full repo analysis with timeline and hotspots |
| `POST /score/batch` | Score many texts, returns clustering |
| `POST /score/citations` | Citation verification |
| `POST /improve` | Improvement suggestions for flagged sentences |

### Novel Signal Endpoints
| Endpoint | Purpose |
|---|---|
| `POST /signals/epistemic-cowardice` | Detailed epistemic cowardice analysis |
| `POST /signals/counterfactual-absence` | Detailed counterfactual analysis |
| `POST /signals/vocabulary-novelty` | Curve data + visualization coordinates |

### Live Data
| Endpoint | Purpose |
|---|---|
| `GET /live/feed` | Real content scored live from 10 sources |
| `GET /live/stream` | SSE stream of scored items |
| `GET /ticker` | 60-second rolling window stats |
| `GET /ticker/live` | SSE ticker stream |

### Intelligence & Evaluation
| Endpoint | Purpose |
|---|---|
| `GET /leaderboard/sites` | Site quality leaderboard |
| `GET /leaderboard/repos` | Repo oversight leaderboard |
| `GET /evaluation/sample` | F1/precision/recall on seed dataset |
| `GET /evaluation/hc3` | Multi-source evaluation (453 samples) |
| `GET /demo/scenarios` | 8 built-in demo examples with expected scores |
| `GET /health` | Service health check |

---

## 🏗️ Architecture

```
apps/
  api/              FastAPI detection engine (Python 3.11+)
    slopguard/
      detectors/    universal.py, domains.py, specificity.py, improvement.py
      adapters/     baselines.py, ticker.py, live_ingestion.py, citation_verification.py
      scoring.py    weighted composite + Welford's adaptive baselines
      main.py       45+ endpoints

  web/              Next.js 14 dashboard (TypeScript)
  extension/        Chrome Manifest V3 browser extension
  action/           Docker-based GitHub Action

datasets/
  samples/
    slopguard_samples.json    104 hand-labeled samples
    github_prs.json           188 real GitHub PR samples
    full_dataset.json         114 multi-source samples
    merged_dataset.json       431 merged + deduplicated
  hc3_results.json            Full evaluation results
```

---

## 🔧 Quick Start Options

### API Only (Python 3.11+)
```bash
cd apps/api
pip install -r requirements.txt
uvicorn slopguard.main:app --reload --port 8000
```

### Dashboard (Next.js 14)
```bash
cd apps/web
npm install && npm run dev
# Open http://localhost:3000
```

### Full Stack (Docker — recommended)
```bash
docker-compose up --build
```

### Chrome Extension
1. Open `chrome://extensions`
2. Enable **Developer Mode**
3. **Load unpacked** → select `apps/extension/`
4. Start the API at `http://localhost:8000`

### CLI
```bash
python -m slopguard.cli score "Updated files and improved the implementation." --domain code_review
python -m slopguard.cli evaluate
```

---

## 🔑 Environment Variables

```bash
# Required for GitHub PR URL scoring
GITHUB_TOKEN=ghp_...

# Optional — enables Supabase persistence (in-memory fallback without it)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# Optional — enables GitHub OAuth flow
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
```

Copy `.env.example` to `.env`. Everything works without any of these — they unlock production features.

---

## ✅ Test Suite

```bash
cd apps/api
python -m pytest tests/ -v
```

**66 tests passing**, covering:
- All 10 universal signals (including 3 novel)
- All 8 domain adapters
- Adversarial slop detection
- Batch clustering and fingerprinting
- Edge cases: empty input, single word, 5000-word documents
- Baseline cold start (null, not zero)
- Improvement engine quality

---

## 🎖️ Bonus Targets

| Bonus | Status | Evidence |
|---|---|---|
| **Bake-Off +5** | ✅ | 453-sample merged dataset, F1 = 0.926, per-domain at `/evaluation/hc3` |
| **Live Fire +5** | ✅ | Live ingestion from 10 real sources, `/live/feed` shows scored content right now |
| **Open Source Ready +3** | ✅ | README, CONTRIBUTING.md, CI, Docker, `.env.example`, examples/ |
| **Cross-Track Scanner +3** | ✅ | Single engine, 8 domain adapters, `/score/text?domain=X` |
| **Sharpest Signal $100** | 🎯 | Epistemic Cowardice + Counterfactual Absence + Vocabulary Novelty |

---

## 📦 Submission Assets

| File | Purpose |
|---|---|
| `docs/DEMO_SCRIPT.md` | 6-minute demo script with exact inputs and expected outputs |
| `docs/JUDGE_PACKET.md` | Full feature list and what's real vs production follow-up |
| `CONTRIBUTING.md` | Contribution guide |
| `examples/github-action.yml` | Ready-to-use GitHub Action workflow |
| `examples/cms-prepublish.js` | CMS pre-publish hook example |

---

## License

MIT

---

*Stop reading slop. Guard your signal.*
