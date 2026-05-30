# Product Requirements Document: SlopGuard

**The Internet's Quality Layer**

A browser extension + API platform that scores every piece of content you read
for human oversight across all 8 surfaces where AI slop does real damage.

Prepared by Urjit Upadhyay  
Flutter & MERN Stack Developer | urjitupadhyayuu@gmail.com  
Slop Scan Hackathon 2026 | May 29 - Jun 1, 2026

## 01. Executive Summary

The internet has a quality problem that nobody is solving at the infrastructure
level. Tools like GPTZero and Originality.ai ask the wrong question: "was this
written by AI?" The right question is: **did a human actually check this before
hitting publish?**

SlopGuard answers that question everywhere, passively, without interrupting you.

It is a browser extension backed by a multi-signal detection engine that lives
in your browser and scores content you encounter: GitHub PRs, documentation,
cover letters, Slack messages, academic papers, marketplace reviews, news
articles, and social posts. The score is for human oversight quality, not AI
authorship.

## Key Facts

| Item | Decision |
| --- | --- |
| Hackathon coverage | Tracks A-H |
| Primary deliverable | Chrome extension + dashboard + FastAPI engine |
| Target users | Engineers, HR teams, researchers, consumers, journalists |
| Differentiator | Human oversight scoring, not AI detection |
| Team size | 1 developer (solo) |
| Bonus targets | Live Fire, Cross-Track Scanner, Open Source Ready, Bake-Off |

## 02. The Problem

AI writes everything now: code, docs, reviews, papers, news, and cover letters.
The question that matters is whether a human exercised judgment before
publishing.

A PR description written by Copilot and reviewed carefully by a senior engineer
can be useful. A PR description written by Copilot and pushed unread is slop.
The difference is human judgment.

## 03. The Solution

SlopGuard measures human oversight through signals that are hard to fake without
doing the actual work:

- Does the content explain why, or merely what?
- Does it add details that are not already obvious?
- Does it include concrete examples, numbers, risks, tradeoffs, or citations?
- Does it look structurally templated across a batch?
- Did review comments actually lead to changes?
- Does the content drift from the underlying code, claim, product, or source?

## 04. Platform Architecture

### Layer 1: Browser Extension

Chrome Manifest V3 extension that scans visible content blocks and overlays a
small quality indicator: green, yellow, red, or gray.

### Layer 2: SlopGuard Dashboard

Next.js web app for demoing text scoring, batch similarity, repo oversight,
hiring pipeline analysis, and academic verification reports.

### Layer 3: SlopGuard API

FastAPI service exposing scoring endpoints for the extension, dashboard, CI/CD,
Slack bots, VS Code, and CMS plugins.

### Layer 4: Public Leaderboards

Weekly trust scores for domains, repositories, publishers, and marketplaces.

## 05. Detection Engine

### Universal Signals

| Signal | Measures | Technical Approach |
| --- | --- | --- |
| Information Density | How much text carries actual information | Shannon entropy, compression ratio, sentence-level novelty, stop-word ratio, lexical diversity |
| WHY vs WHAT | Reasoning vs description | causal connectives, conditional reasoning, comparisons, tradeoffs, sentence depth analysis |
| Human Delta | Active human engagement with content | editing artifacts (corrections, hedging, disagreement markers), contractions, first-person references |
| Template Structure | Repeated/formulaic structure | sentence-length CoV, opener repetition, AI transition phrases, paragraph uniformity, voice consistency |
| Semantic Uniqueness | Distance from known slop patterns | Jensen-Shannon trigram divergence from AI-slop baseline, hapax legomena ratio, bigram novelty |
| Specificity | Concrete technical references | per-sentence detection of numbers, filenames, inline code, system keywords, camelCase identifiers |

### Domain Signals

| Track | Signals Implemented |
| --- | --- |
| A Code Review | PR diff divergence (TF-IDF overlap), reviewer impact (engagement patterns), code comment intelligence, commit reasoning ratio, slop velocity proxy |
| B Docs | circular explanation (3-sentence sliding window entity overlap), example density, heading-to-content ratio, codebase drift proxy |
| C Hiring | batch similarity (TF-IDF + structural fingerprinting), company specificity, achievement specificity, template detection, batch structural fingerprint |
| D Communications | decision/action density, compression score, reply information score, meeting notes substance |
| E Content & SEO | originality proxy, claim specificity, time-to-value, structure rehash |
| F Academia | academic grounding, citation claim alignment, style consistency (sliding window feature drift), self-citation inflation |
| G Marketplaces | review specificity, reviewer authenticity proxy, temporal clustering proxy |
| H Social & News | rage bait fingerprint (emotional triggers + caps abuse), network coordination proxy, posting cadence proxy, engagement authenticity proxy |

## 06. Product Features

### Extension

- Works on every website automatically.
- Runs client-side checks where possible.
- Calls the API for deeper scoring.
- Never blocks content or shames authors.
- Explains exactly which signals triggered.

### Dashboard

- Paste text and get a signal breakdown.
- Paste PR metadata and diff.
- Upload batches of reviews, resumes, or cover letters.
- View cluster warnings and sample confusion matrix.
- Show site and repo leaderboards.

### API

| Endpoint | Input | Output |
| --- | --- | --- |
| `POST /score/text` | text + domain | score + signal breakdown |
| `POST /score/pr` | PR description + diff | PR oversight report |
| `POST /score/batch` | array of texts | clusters + per-item scores |
| `POST /score/citations` | DOI/title list | citation status report |
| `POST /citations/verify` | DOI/title list | CrossRef + Semantic Scholar + PubMed results |
| `GET /leaderboard/sites` | optional category | site trust rankings |
| `GET /leaderboard/repos` | optional org | repo oversight rankings |
| `POST /telemetry/score` | user_id + score event | persisted via Supabase or in-memory |
| `POST /telemetry/feedback` | user_id + feedback | persisted via Supabase or in-memory |
| `GET /telemetry/summary/{user_id}` | user_id | aggregated score summary |
| `GET /auth/github/url` | — | OAuth authorization URL |
| `POST /github/timeline` | token + owner + repo | PR timeline data |
| `POST /github/velocity` | token + owner + repo | Slop Velocity computation |
| `GET /adapters/status` | — | which production adapters are active |

## 07. Technology Stack

| Layer | Technology |
| --- | --- |
| Browser extension | Chrome Manifest V3, vanilla JavaScript, CSS |
| Dashboard | Next.js 16, React 18, TypeScript |
| Detection API | FastAPI, Python, Pydantic |
| NLP (deterministic) | scikit-learn (TF-IDF), Jensen-Shannon divergence, Shannon entropy, CoV analysis |
| NLP (production) | sentence-transformers (semantic embedding), RoBERTa zero-shot (WHY/WHAT classification) |
| Vector store | FAISS IVF index for large-scale batch clustering |
| Graph analysis | NetworkX for documentation circularity cycle detection |
| AST parsing | Tree-sitter for code comment intelligence (Python, JS, TS) |
| Citation APIs | CrossRef, Semantic Scholar, PubMed (E-utilities) |
| Persistence | Supabase (opt-in telemetry, cross-device sync, user profiles) |
| OAuth | GitHub OAuth for PR timeline ingestion & real Slop Velocity |
| Data | 104 labeled samples across 9 domains, evaluation harness |
| Deployment | Vercel + Railway |

### What Ships (All Adapters Implemented)
- 6 universal signals: deterministic baseline + optional ML upgrades (sentence-transformers, RoBERTa)
- 8 domain adapters with 30+ domain-specific signals
- Batch clustering: structural fingerprint → TF-IDF → FAISS+embedding (progressive enhancement)
- Code comment intelligence: regex fallback → Tree-sitter AST parsing
- Documentation circularity: sliding window → NetworkX graph cycle detection
- Citation verification: CrossRef + Semantic Scholar + PubMed APIs
- GitHub OAuth for real PR timeline data and Slop Velocity computation
- Supabase for opt-in telemetry, feedback, and cross-device sync
- Explainable scoring: every signal returns reason + detail strings

### Production Followups (Post-Hackathon)
- Fine-tune RoBERTa on labeled WHY/WHAT dataset (currently uses zero-shot BART)
- Deploy FAISS index on GPU for sub-millisecond similarity search at scale
- Publish Chrome Extension to Chrome Web Store
- Add live leaderboards backed by Supabase telemetry
- Expand Tree-sitter to Go, Java, Rust parsers
- Add GitHub Actions integration for CI/CD PR scoring

## 08. Scoring Alignment

SlopGuard is built to match the hackathon scoring:

- **Detection Accuracy:** multi-signal scoring with honest false positives.
- **Practical Usefulness:** passive extension and API integrations.
- **Technical Execution:** separated API, extension, dashboard, and adapters.
- **Innovation:** human oversight scoring, human delta, Slop Velocity Timeline.
- **Presentation:** live fire demo across recognizable real surfaces.

## 09. Closing Note

SlopGuard is not anti-AI. It is anti-unreviewed output. It makes low-effort
content visible so humans can make better decisions.

