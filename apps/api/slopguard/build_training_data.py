#!/usr/bin/env python
"""Training data builder for SlopGuard novel signals.

Generates a large labeled dataset targeting the three novel signals:
  1. Epistemic Cowardice (committed vs cowardly)
  2. Counterfactual Absence (rich reasoning vs happy path)
  3. Vocabulary Novelty (progressive vs flat)

Also generates WHY/WHAT training data for the RoBERTa classifier.

Usage:
    python -m slopguard.build_training_data
    python -m slopguard.build_training_data --output datasets/training
    python -m slopguard.build_training_data --train-roberta
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

random.seed(42)

# =============================================================================
# SECTION 1 — Epistemic Cowardice training pairs
# Each pair: (cowardly_text, committed_text) on the same topic
# =============================================================================

EPISTEMIC_PAIRS = [
    # --- Caching ---
    (
        "You might want to consider using Redis for caching, depending on your use case. "
        "It could potentially improve performance in some scenarios, though results may vary. "
        "Some developers believe it's better than Memcached, but others prefer different solutions. "
        "Your mileage may vary. It depends on your specific requirements.",
        "Don't use Memcached for new projects. Redis does everything Memcached does plus pub/sub, "
        "Lua scripting, and sorted sets. We migrated in 2023 and haven't looked back. "
        "Use Redis. The only reason to pick Memcached is if you're already running it and the "
        "migration cost isn't worth it."
    ),
    # --- Database choice ---
    (
        "There are various database options available, each with their own advantages and disadvantages. "
        "PostgreSQL may be suitable for some use cases, while MySQL might work better in others. "
        "It is generally accepted that the choice depends on your specific needs. "
        "Consulting with your team to evaluate the tradeoffs would be advisable.",
        "Use PostgreSQL. MySQL's default transaction isolation is READ COMMITTED which causes "
        "phantom reads — we hit this in production on the orders table. PostgreSQL defaults to "
        "READ COMMITTED too but its MVCC implementation is cleaner. If you need full-text search, "
        "Postgres has it built in. Don't use MySQL for new projects."
    ),
    # --- Authentication ---
    (
        "Authentication is an important aspect of application security. There are various approaches "
        "that could potentially work, depending on your requirements. JWT tokens may be suitable "
        "in some cases, while session-based auth might be more appropriate in others. "
        "It is worth noting that security considerations should be carefully evaluated.",
        "Use session tokens stored in httpOnly cookies, not JWTs in localStorage. "
        "JWTs in localStorage are readable by any JavaScript on the page — one XSS vulnerability "
        "and every user token is compromised. Sessions with Redis backing give you instant revocation. "
        "JWTs are stateless which sounds good until you need to log someone out immediately."
    ),
    # --- Deployment ---
    (
        "There are multiple deployment strategies that teams might consider. Blue-green deployments "
        "could potentially reduce downtime in some scenarios. Canary releases might be more suitable "
        "for certain use cases. The best approach may vary depending on your infrastructure.",
        "Use canary releases, not blue-green, for stateful services. Blue-green requires you to "
        "run two full production environments simultaneously — that's 2x cost. Canary lets you "
        "route 5% of traffic to the new version, watch error rates for 10 minutes, then promote. "
        "We've caught 3 regressions this way in the last year that would have been full outages."
    ),
    # --- Code review ---
    (
        "Code review practices can vary significantly across teams. Some developers prefer detailed "
        "reviews while others may find them time-consuming. There are various factors to consider "
        "when establishing review processes. It depends on your team's specific needs and culture.",
        "Require at least one approval from someone who didn't write the code. No exceptions. "
        "We tried 'optional review for small changes' for 3 months — it produced 4 production bugs "
        "that a second pair of eyes would have caught. The overhead is 15 minutes per PR. "
        "The cost of a production incident is 4 hours minimum."
    ),
    # --- Testing ---
    (
        "Testing strategies can vary depending on the project. Unit tests might be beneficial "
        "in some cases, while integration tests could be more appropriate in others. "
        "Some teams prefer TDD while others find it less suitable. Results may vary.",
        "Write integration tests, not unit tests, for database code. Unit tests with mocked "
        "database calls test your mock, not your SQL. We had 100% unit test coverage on the "
        "billing module and still shipped a query that returned wrong results on NULL amounts. "
        "Integration tests against a real Postgres instance caught it in 2 minutes."
    ),
    # --- Logging ---
    (
        "Logging is an important consideration for production systems. There are various logging "
        "frameworks available that might suit different needs. Structured logging could potentially "
        "be beneficial in some scenarios. The appropriate approach depends on your requirements.",
        "Use structured JSON logging from day one. We spent 3 days parsing unstructured logs "
        "after the March incident because grep couldn't correlate request IDs across services. "
        "JSON logs with request_id, user_id, and duration fields let you write a CloudWatch "
        "Insights query in 30 seconds. The migration cost from printf-style logging is a week."
    ),
    # --- API design ---
    (
        "API design is a complex topic with many considerations. RESTful APIs may be suitable "
        "for some use cases while GraphQL might work better in others. Various factors should "
        "be considered when making this decision. It is generally advisable to consult with "
        "your team and evaluate the specific requirements.",
        "Use REST for public APIs, GraphQL for internal product APIs. REST is simpler to cache, "
        "document, and version. GraphQL is better when clients need flexible queries — our mobile "
        "app was making 7 REST calls per screen, GraphQL reduced it to 1. Don't use GraphQL "
        "for a public API — the introspection endpoint is a security liability."
    ),
]

# =============================================================================
# SECTION 2 — Counterfactual training pairs
# Each pair: (happy_path, rich_counterfactuals) on the same topic
# =============================================================================

COUNTERFACTUAL_PAIRS = [
    # --- Caching ---
    (
        "Added Redis caching to improve performance. The system now stores frequently accessed "
        "data in memory, reducing database load. Performance is improved and users will experience "
        "faster response times. The implementation follows best practices for caching.",
        "Added Redis caching for the user profile endpoint. Considered Memcached but rejected it "
        "because we need pub/sub for cache invalidation when profiles update. TTL set to 300s — "
        "shorter would hammer the DB on cache miss storms, longer risks showing stale data after "
        "password changes. Known limitation: cache doesn't invalidate on admin edits. "
        "Accepted that risk, added a manual flush endpoint for the support team."
    ),
    # --- Authentication ---
    (
        "Implemented JWT authentication to secure the API. The system now validates tokens "
        "on each request. Security is improved and users can authenticate safely. "
        "The implementation follows industry best practices.",
        "Fixed JWT secret exposure in auth/middleware.js — previous implementation logged the "
        "full token on line 47, appearing in CloudWatch logs. Considered environment variables "
        "but rejected that because our pipeline doesn't support secret rotation. Switched to "
        "AWS Secrets Manager with 30-day rotation. This breaks if Secrets Manager API is "
        "unavailable — added 5s timeout with fallback to cached credentials. "
        "Edge case: if cache is empty AND Secrets Manager is down, auth fails. Accepted that risk."
    ),
    # --- Database migration ---
    (
        "Migrated the database to improve performance and scalability. The new schema is more "
        "efficient and better organized. Query performance is improved across the board. "
        "The migration was completed successfully.",
        "Migrated orders table from UUID primary keys to BIGINT GENERATED ALWAYS AS IDENTITY. "
        "UUID PKs caused 40% index bloat on the 12M-row table — measured via pg_stat_user_tables. "
        "Considered keeping UUIDs with a separate surrogate key but rejected it: double the index "
        "size. Migration ran in 3 hours with zero downtime using pg_repack. "
        "Known limitation: external systems using UUID references need a mapping table for 90 days."
    ),
    # --- Rate limiting ---
    (
        "Implemented rate limiting to protect the API from abuse. The system now limits "
        "requests per user. This improves reliability and prevents overload. "
        "The implementation is robust and scalable.",
        "Added rate limiting to /api/v2/search after Grafana showed 3 customers sending 400+ rps, "
        "spiking p99 from 120ms to 2.8s. Limit: 60 rps/key with 429 + Retry-After header. "
        "Considered token bucket vs sliding window — chose sliding window because token bucket "
        "allows burst spikes at window boundaries. Limitation: limits are per-instance, not "
        "cluster-wide. Under 10 instances, a determined client can send 600 rps total. "
        "Accepted that risk — cluster-wide Redis counter adds 2ms per request."
    ),
    # --- Error handling ---
    (
        "Improved error handling throughout the application. The system now handles errors "
        "more gracefully and provides better feedback to users. Reliability is improved. "
        "The implementation follows best practices.",
        "Replaced generic 500 responses with structured error codes after support spent 2 hours "
        "on a ticket that turned out to be a missing required field. Now returns "
        "{code: 'MISSING_FIELD', field: 'billing_address', message: '...'}. "
        "Considered using HTTP 422 vs 400 — chose 400 because our iOS client treats 422 as "
        "network error. Known gap: validation errors on nested objects don't include the path "
        "(e.g., 'items[2].price' not 'price'). Fix in next sprint."
    ),
    # --- Deployment ---
    (
        "Updated the deployment process to improve reliability. The new process is more "
        "streamlined and reduces downtime. Deployments are now faster and more consistent. "
        "The implementation follows DevOps best practices.",
        "Switched from rolling deploys to blue-green after the March 14 incident where a "
        "bad deploy caused 8 minutes of mixed responses (old and new code serving simultaneously). "
        "Blue-green costs 2x EC2 during deploy window (~15 min, ~$0.40 per deploy). "
        "Considered canary releases but rejected them — our session store isn't compatible with "
        "mixed versions. Limitation: database migrations must be backward-compatible with the "
        "old version for the 15-minute overlap window."
    ),
    # --- Monitoring ---
    (
        "Added monitoring to improve system observability. The system now tracks key metrics "
        "and alerts on issues. This improves reliability and helps the team respond faster. "
        "The implementation provides comprehensive visibility.",
        "Added p95/p99 latency alerts after we missed a 3x slowdown for 4 hours because "
        "average latency looked fine (fast requests masked slow ones). Thresholds: p95 > 500ms "
        "pages on-call, p99 > 2s pages the whole team. Considered percentile vs average — "
        "average is useless for latency. Known limitation: alerts fire on deploy spikes. "
        "Added 5-minute suppression window after deploys. This means we're blind for 5 minutes "
        "post-deploy — accepted that risk."
    ),
    # --- Connection pooling ---
    (
        "Implemented connection pooling to improve database performance. The system now "
        "reuses connections efficiently. This reduces overhead and improves throughput. "
        "The implementation is optimized for production use.",
        "Added PgBouncer connection pooling after the payments service exhausted Postgres's "
        "100-connection limit at 400 concurrent users — measured via pg_stat_activity. "
        "Considered increasing max_connections but rejected it: each Postgres connection uses "
        "~5MB RAM, 500 connections = 2.5GB just for connection overhead. PgBouncer in "
        "transaction mode reduced connections from 400 to 12. Limitation: transaction-mode "
        "pooling breaks prepared statements — had to disable them in the ORM config."
    ),
]

# =============================================================================
# SECTION 3 — WHY/WHAT training data for RoBERTa fine-tuning
# Expanded from the existing synthetic set with domain-specific examples
# =============================================================================

WHY_SENTENCES = [
    # Code review — specific
    "because profiling showed 340ms overhead in the auth middleware",
    "since the connection pool exhausted at 400 concurrent users",
    "to prevent the JWT secret from appearing in CloudWatch logs",
    "because the UUID primary keys caused 40% index bloat on the orders table",
    "since Redis pub/sub is required for cache invalidation on profile updates",
    "to avoid the thundering herd problem on cache miss storms",
    "because the rolling deploy caused 8 minutes of mixed responses",
    "since p99 latency spiked from 120ms to 2.8s under load",
    "to handle the case where Secrets Manager API is unavailable",
    "because prepared statements are incompatible with PgBouncer transaction mode",
    # Code review — qualitative but genuine
    "because the previous implementation was not thread-safe",
    "since the old approach didn't handle NULL amounts correctly",
    "to ensure backward compatibility during the 15-minute deploy window",
    "because the test suite was mocking the database instead of testing real queries",
    "since the error messages were too generic for support to diagnose issues",
    # Docs
    "because the migration takes 12 minutes on a 50GB database",
    "since the circuit breaker opens after 3 consecutive failures",
    "to prevent full table scans on the audit_logs table",
    "because the retry mechanism uses exponential backoff starting at 200ms",
    "since the session secret must be at least 32 characters",
    # Academia
    "because the benchmark over-represents STEM domains",
    "since the ablation showed a 3.2 point F1 drop without attention pooling",
    "to control for multiple comparisons using Bonferroni correction",
    "because the dataset contains potential PII from Reddit posts",
    "since the within-subjects design reduces between-participant variance",
    # General causal
    "because it was causing memory leaks in production",
    "since the previous version broke when the queue depth exceeded 10k messages",
    "to reduce the number of database round trips from 7 to 1",
    "because the old implementation didn't handle concurrent writes correctly",
    "since the cache TTL was too short, causing unnecessary database load",
]

WHAT_SENTENCES = [
    # Code review
    "updated the authentication module",
    "added Redis caching to the user profile endpoint",
    "fixed the JWT secret exposure bug",
    "migrated the orders table to BIGINT primary keys",
    "implemented rate limiting on the search API",
    "replaced generic 500 responses with structured error codes",
    "switched from rolling deploys to blue-green deployments",
    "added p95 and p99 latency alerts",
    "implemented PgBouncer connection pooling",
    "refactored the billing retry logic",
    # Docs
    "updated the deployment documentation",
    "added configuration examples to the README",
    "created a troubleshooting guide for common errors",
    "updated the API reference with new endpoints",
    "added a migration guide for version 2.0",
    # General
    "bumped the dependency to version 3.1.4",
    "renamed the function to match the new naming convention",
    "removed the unused import statements",
    "added unit tests for the new feature",
    "updated the changelog with recent changes",
    "created a new service for handling webhooks",
    "modified the configuration to support multiple environments",
    "added logging to the payment processing module",
    "fixed a typo in the error message",
    "updated the CI pipeline to run on pull requests",
]

NEUTRAL_SENTENCES = [
    "the function returns a boolean value",
    "this module handles user authentication",
    "the API supports JSON and XML formats",
    "the database schema includes a users table",
    "the service runs on port 8080 by default",
    "the configuration file is located at config/settings.py",
    "the test suite includes 47 test cases",
    "the deployment uses Docker containers",
    "the application requires Python 3.11 or higher",
    "the repository follows the GitFlow branching strategy",
]

# =============================================================================
# SECTION 4 — Augmentation helpers
# =============================================================================

_HEDGE_PREFIXES = [
    "You might want to consider ", "It could potentially ", "In some cases, ",
    "Depending on your use case, ", "It may be worth noting that ",
    "Some developers believe that ", "It is generally accepted that ",
    "Results may vary, but ", "Your mileage may vary — ",
]

_COMMIT_PREFIXES = [
    "Don't use ", "Use ", "Always ", "Never ", "We recommend ",
    "Switch to ", "Avoid ", "The correct approach is to ",
]

_FAILURE_PREFIXES = [
    "This breaks when ", "Known limitation: ", "Edge case: ",
    "Caveat: ", "This fails if ", "Doesn't handle ",
    "Accepted that risk — ", "Limitation: ",
]

_ALTERNATIVE_PREFIXES = [
    "Considered X but rejected it because ", "Instead of X, we chose Y because ",
    "We tried X and it failed — ", "Switched from X to Y because ",
    "Rejected X because ", "Went with Y over X because ",
]


def augment_with_hedges(text: str, n: int = 3) -> list[str]:
    """Add hedge prefixes to create cowardly variants."""
    results = []
    for prefix in random.sample(_HEDGE_PREFIXES, min(n, len(_HEDGE_PREFIXES))):
        # Lower-case first char of text if prefix ends with space
        t = text[0].lower() + text[1:] if text else text
        results.append(prefix + t)
    return results


def augment_with_commitments(text: str, n: int = 3) -> list[str]:
    """Add commitment prefixes to create strong-position variants."""
    results = []
    for prefix in random.sample(_COMMIT_PREFIXES, min(n, len(_COMMIT_PREFIXES))):
        results.append(prefix + text)
    return results


def augment_with_failure_modes(text: str, n: int = 3) -> list[str]:
    """Add failure mode prefixes to create counterfactual variants."""
    results = []
    for prefix in random.sample(_FAILURE_PREFIXES, min(n, len(_FAILURE_PREFIXES))):
        results.append(prefix + text)
    return results

# =============================================================================
# SECTION 5 — Dataset builders
# =============================================================================

def build_epistemic_dataset() -> list[dict]:
    """Build labeled dataset for epistemic cowardice signal."""
    samples = []

    for cowardly, committed in EPISTEMIC_PAIRS:
        samples.append({"text": cowardly, "label": "cowardly", "signal": "epistemic_cowardice"})
        samples.append({"text": committed, "label": "committed", "signal": "epistemic_cowardice"})

        # Augment cowardly with more hedges
        for aug in augment_with_hedges(cowardly[:200], n=2):
            samples.append({"text": aug, "label": "cowardly", "signal": "epistemic_cowardice"})

        # Augment committed with commitment prefixes
        for aug in augment_with_commitments(committed[:200], n=2):
            samples.append({"text": aug, "label": "committed", "signal": "epistemic_cowardice"})

    return samples


def build_counterfactual_dataset() -> list[dict]:
    """Build labeled dataset for counterfactual absence signal."""
    samples = []

    for happy_path, rich in COUNTERFACTUAL_PAIRS:
        samples.append({"text": happy_path, "label": "absent", "signal": "counterfactual_absence"})
        samples.append({"text": rich, "label": "present", "signal": "counterfactual_absence"})

        # Augment happy path with more generic language
        samples.append({
            "text": happy_path + " The implementation follows best practices and is production-ready.",
            "label": "absent",
            "signal": "counterfactual_absence",
        })

        # Augment rich with more failure modes
        for aug in augment_with_failure_modes(rich[:200], n=2):
            samples.append({"text": aug, "label": "present", "signal": "counterfactual_absence"})

    return samples


def build_whywhat_dataset() -> list[dict]:
    """Build WHY/WHAT labeled dataset for RoBERTa fine-tuning."""
    samples = []

    for text in WHY_SENTENCES:
        samples.append({"text": text, "label": "why"})
        # Augment with variations
        for aug in augment_with_hedges(text, n=1):
            samples.append({"text": aug, "label": "why"})  # hedged WHY is still WHY

    for text in WHAT_SENTENCES:
        samples.append({"text": text, "label": "what"})

    for text in NEUTRAL_SENTENCES:
        samples.append({"text": text, "label": "neutral"})

    # Add the existing synthetic patterns from finetune_roberta.py
    why_templates = [
        "because {X} was causing {Y}",
        "since {X} led to {Y}",
        "to prevent {X} from happening",
        "therefore we needed to {X}",
        "due to {X} affecting {Y}",
        "because profiling showed {X}ms latency",
        "to avoid {X} issues in production",
        "because {X} broke when {Y}",
        "to reduce {X} by {Y}%",
        "since we noticed {X} in production",
    ]
    what_templates = [
        "updated the {X} module",
        "added {X} functionality",
        "fixed {X} bug",
        "implemented {X} feature",
        "refactored {X} class",
        "bumped {X} to version {Y}",
        "added tests for {X}",
        "created a new {X} service",
        "modified {X} to handle {Y}",
        "removed unused {X} code",
    ]
    fillers = {
        "X": ["auth", "billing", "cache", "database", "api", "middleware",
              "parser", "validator", "handler", "router", "service"],
        "Y": ["timeout", "errors", "latency", "crashes", "duplicates",
              "memory leaks", "race conditions", "overflow"],
    }

    for template in why_templates:
        for _ in range(30):
            text = template
            for key, values in fillers.items():
                text = text.replace("{" + key + "}", random.choice(values))
            samples.append({"text": text, "label": "why"})

    for template in what_templates:
        for _ in range(30):
            text = template
            for key, values in fillers.items():
                text = text.replace("{" + key + "}", random.choice(values))
            samples.append({"text": text, "label": "what"})

    random.shuffle(samples)
    return samples

# =============================================================================
# SECTION 6 — Scoring calibration dataset
# Used to verify signal separation before demo
# =============================================================================

CALIBRATION_CASES = [
    {
        "name": "AI hedge fest",
        "text": (
            "This approach may have performance implications depending on your use case. "
            "There are various factors to consider, and different teams have different needs. "
            "It could potentially work well in some scenarios, though in other cases alternative "
            "approaches might be more suitable. Consulting with your team to evaluate the "
            "tradeoffs would be advisable."
        ),
        "domain": "code_review",
        "expected_score_max": 50,
        "expected_label": "low",
        "expected_signals": {
            "epistemic_cowardice": {"max": 0.35},
            "counterfactual_absence": {"max": 0.30},
        },
    },
    {
        "name": "Human strong position",
        "text": (
            "Don't use this pattern in production. We tried it on the payments service and it "
            "caused a 3x increase in database connections under load. The connection pool "
            "exhausted at 400 concurrent users. Use the repository pattern instead — it's more "
            "verbose but the connection lifecycle is explicit and testable."
        ),
        "domain": "code_review",
        "expected_score_min": 50,
        "expected_label": "mixed",
        "expected_signals": {
            "epistemic_cowardice": {"min": 0.55},
            "counterfactual_absence": {"min": 0.25},
        },
    },
    {
        "name": "AI happy path",
        "text": (
            "Implemented the caching layer using Redis. The system now stores frequently accessed "
            "data in memory, reducing database load. Performance is improved and users will "
            "experience faster response times. The implementation follows best practices for caching."
        ),
        "domain": "code_review",
        "expected_score_max": 52,
        "expected_label": "low",
        "expected_signals": {
            "counterfactual_absence": {"max": 0.20},
        },
    },
    {
        "name": "Human with counterfactuals",
        "text": (
            "Added Redis caching for the user profile endpoint. Considered Memcached but rejected "
            "it because we need pub/sub for cache invalidation when profiles update. TTL set to "
            "300s — shorter would hammer the DB on cache miss storms, longer risks showing stale "
            "data after password changes. Known limitation: cache doesn't invalidate on admin edits. "
            "Accepted that risk, added a manual flush endpoint for support team."
        ),
        "domain": "code_review",
        "expected_score_min": 58,
        "expected_label": "mixed",
        "expected_signals": {
            "counterfactual_absence": {"min": 0.40},
            "epistemic_cowardice": {"min": 0.45},
        },
    },
]


def run_calibration() -> dict:
    """Run calibration check and return pass/fail for each case."""
    from slopguard.scoring import score_text

    results = []
    all_pass = True

    print("\n" + "=" * 60)
    print("SIGNAL CALIBRATION CHECK")
    print("=" * 60)

    for case in CALIBRATION_CASES:
        r = score_text(case["text"], case["domain"])
        signal_map = {s.name: s.score for s in r.signals}

        checks = []

        # Score checks
        if "expected_score_min" in case:
            ok = r.score >= case["expected_score_min"]
            checks.append(("score_min", ok, f"{r.score:.1f} >= {case['expected_score_min']}"))
            if not ok:
                all_pass = False
        if "expected_score_max" in case:
            ok = r.score <= case["expected_score_max"]
            checks.append(("score_max", ok, f"{r.score:.1f} <= {case['expected_score_max']}"))
            if not ok:
                all_pass = False

        # Signal checks
        for sig_name, thresholds in case.get("expected_signals", {}).items():
            sig_score = signal_map.get(sig_name, -1)
            if "min" in thresholds:
                ok = sig_score >= thresholds["min"]
                checks.append((f"{sig_name}_min", ok, f"{sig_score:.3f} >= {thresholds['min']}"))
                if not ok:
                    all_pass = False
            if "max" in thresholds:
                ok = sig_score <= thresholds["max"]
                checks.append((f"{sig_name}_max", ok, f"{sig_score:.3f} <= {thresholds['max']}"))
                if not ok:
                    all_pass = False

        status = "✅ PASS" if all(c[1] for c in checks) else "❌ FAIL"
        print(f"\n{status}  {case['name']}: {r.score:.1f} ({r.oversight})")
        for sig in ["epistemic_cowardice", "counterfactual_absence", "vocabulary_novelty"]:
            if sig in signal_map:
                print(f"       {sig}: {signal_map[sig]:.3f}")
        for check_name, ok, detail in checks:
            mark = "  ✓" if ok else "  ✗"
            print(f"  {mark} {check_name}: {detail}")

        results.append({
            "name": case["name"],
            "score": r.score,
            "oversight": r.oversight,
            "signals": {s.name: s.score for s in r.signals},
            "checks": [{"name": c[0], "pass": c[1], "detail": c[2]} for c in checks],
        })

    print("\n" + "=" * 60)
    print(f"CALIBRATION: {'✅ ALL PASS' if all_pass else '❌ FAILURES DETECTED'}")
    print("=" * 60 + "\n")

    return {"all_pass": all_pass, "results": results}

# =============================================================================
# SECTION 7 — RoBERTa fine-tuning runner
# =============================================================================

def train_roberta(dataset_path: str, output_dir: str = "models/whywhat-roberta-v2"):
    """Fine-tune RoBERTa on the expanded WHY/WHAT dataset."""
    try:
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            TrainingArguments,
            Trainer,
            DataCollatorWithPadding,
        )
        from datasets import Dataset as HFDataset
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
    except ImportError:
        print("Missing ML dependencies. Install with:")
        print("  pip install transformers datasets accelerate torch scikit-learn")
        return None

    LABEL_MAP = {"why": 0, "what": 1, "neutral": 2}
    ID_MAP = {0: "why", 1: "what", 2: "neutral"}

    # Load dataset
    examples = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            label = item.get("label", "neutral").lower()
            if label in LABEL_MAP:
                examples.append({"text": item["text"], "label": LABEL_MAP[label]})

    print(f"Loaded {len(examples)} examples")
    label_counts = {}
    for ex in examples:
        name = ID_MAP[ex["label"]]
        label_counts[name] = label_counts.get(name, 0) + 1
    print(f"Label distribution: {label_counts}")

    # Split
    train_data, eval_data = train_test_split(
        examples, test_size=0.15, random_state=42,
        stratify=[e["label"] for e in examples]
    )

    tokenizer = AutoTokenizer.from_pretrained("roberta-base")

    def tokenize_fn(batch):
        return tokenizer(batch["text"], truncation=True, max_length=128)

    train_ds = HFDataset.from_list(train_data).map(tokenize_fn, batched=True)
    eval_ds = HFDataset.from_list(eval_data).map(tokenize_fn, batched=True)
    train_ds = train_ds.remove_columns(["text"]).rename_column("label", "labels")
    eval_ds = eval_ds.remove_columns(["text"]).rename_column("label", "labels")

    model = AutoModelForSequenceClassification.from_pretrained(
        "roberta-base", num_labels=3, problem_type="single_label_classification"
    )

    training_args = TrainingArguments(
        output_dir=output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=4,
        weight_decay=0.01,
        warmup_ratio=0.1,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        save_total_limit=2,
        seed=42,
    )

    def compute_metrics(pred):
        labels = pred.label_ids
        preds = pred.predictions.argmax(-1)
        p, r, f1, _ = precision_recall_fscore_support(labels, preds, average="weighted")
        acc = accuracy_score(labels, preds)
        return {"accuracy": acc, "f1": f1, "precision": p, "recall": r}

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
    )

    print(f"\nTraining RoBERTa on {len(train_data)} examples...")
    trainer.train()
    results = trainer.evaluate()
    print(f"\nEval results: {results}")

    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"\nModel saved to {output_dir}")
    print(f"Update roberta_whywhat.py to use: model='{output_dir}'")
    return results

# =============================================================================
# SECTION 8 — Main entry point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Build training data for SlopGuard novel signals")
    parser.add_argument("--output", default="datasets/training", help="Output directory")
    parser.add_argument("--calibrate", action="store_true", help="Run calibration check only")
    parser.add_argument("--train-roberta", action="store_true", help="Fine-tune RoBERTa after building data")
    args = parser.parse_args()

    if args.calibrate:
        run_calibration()
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Building training datasets...")

    # 1. Epistemic cowardice dataset
    ec_data = build_epistemic_dataset()
    ec_path = output_dir / "epistemic_cowardice.jsonl"
    with open(ec_path, "w", encoding="utf-8") as f:
        for item in ec_data:
            f.write(json.dumps(item) + "\n")
    print(f"  Epistemic cowardice: {len(ec_data)} samples → {ec_path}")

    # 2. Counterfactual dataset
    cf_data = build_counterfactual_dataset()
    cf_path = output_dir / "counterfactual_absence.jsonl"
    with open(cf_path, "w", encoding="utf-8") as f:
        for item in cf_data:
            f.write(json.dumps(item) + "\n")
    print(f"  Counterfactual absence: {len(cf_data)} samples → {cf_path}")

    # 3. WHY/WHAT dataset for RoBERTa
    ww_data = build_whywhat_dataset()
    ww_path = output_dir / "whywhat_roberta.jsonl"
    with open(ww_path, "w", encoding="utf-8") as f:
        for item in ww_data:
            f.write(json.dumps(item) + "\n")
    print(f"  WHY/WHAT (RoBERTa): {len(ww_data)} samples → {ww_path}")

    # 4. Combined scoring dataset (for evaluate.py)
    all_scoring = []
    for cowardly, committed in EPISTEMIC_PAIRS:
        all_scoring.append({"text": cowardly, "label": "slop", "domain": "code_review", "source": "training_epistemic"})
        all_scoring.append({"text": committed, "label": "reviewed", "domain": "code_review", "source": "training_epistemic"})
    for happy, rich in COUNTERFACTUAL_PAIRS:
        all_scoring.append({"text": happy, "label": "slop", "domain": "code_review", "source": "training_counterfactual"})
        all_scoring.append({"text": rich, "label": "reviewed", "domain": "code_review", "source": "training_counterfactual"})

    scoring_path = output_dir / "novel_signals_scoring.json"
    with open(scoring_path, "w", encoding="utf-8") as f:
        json.dump(all_scoring, f, indent=2)
    print(f"  Scoring dataset: {len(all_scoring)} samples → {scoring_path}")

    # 5. Run calibration
    print("\nRunning calibration check...")
    cal = run_calibration()

    # 6. Summary
    print(f"\nTotal training samples generated:")
    print(f"  Epistemic cowardice:  {len(ec_data)}")
    print(f"  Counterfactual:       {len(cf_data)}")
    print(f"  WHY/WHAT (RoBERTa):   {len(ww_data)}")
    print(f"  Scoring eval:         {len(all_scoring)}")
    print(f"\nCalibration: {'✅ PASS' if cal['all_pass'] else '❌ NEEDS TUNING'}")

    # 7. Optionally train RoBERTa
    if args.train_roberta:
        print("\nFine-tuning RoBERTa on WHY/WHAT dataset...")
        train_roberta(str(ww_path))

    if not cal["all_pass"]:
        print("\n⚠️  Calibration failed. Check the signal patterns before demo.")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
