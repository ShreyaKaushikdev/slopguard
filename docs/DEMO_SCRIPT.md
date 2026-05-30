# SlopGuard Demo Script

## 0:00 - 0:30: Open the Dashboard

Show `http://127.0.0.1:3000`.

Say:

> SlopGuard does not ask whether this was AI-generated. It asks whether a human
> actually thought about it before publishing.

## 0:30 - 1:30: GitHub PR Analysis

Open the PR tab.

Use the default hollow PR description:

> Updated billing files and improved retry handling. This fixes issues and
> enhances reliability.

Click **Score PR**.

Show:

- WHY vs WHAT ratio
- Concrete detail score
- PR diff divergence
- Weak passage highlighting

Then replace the description with:

> We capped billing retries at 3 because Stripe replayed duplicate webhooks
> during deploys. Added a 10 minute idempotency window and tested replay
> fixtures for 200, 409, and timeout responses.

Click **Score PR** again.

Say:

> The first PR scores around 42 — low oversight, generic language.
> The second scores around 65 — specific, falsifiable reasoning.

## 1:30 - 2:30: Adversarial Slop Detection

This is the **key differentiator**. Show how SlopGuard catches prompt-engineered content.

Open the Scan tab or use the API directly:

**Show AI slop:**
> Refactored the authentication module because it was causing performance issues in production. The new implementation is more robust and provides better error handling for various edge cases.

Say:

> This looks like a real PR description. But SlopGuard's specificity verifier catches it:
> "performance issues" — no numbers. "more robust" — pure adjective.
> "various edge cases" — vague reference. Specificity score: 0.20.

**Show genuine reasoning:**
> Profiling showed auth middleware adding 340ms to every request. Moved token validation from the hot path to a background job using Redis cache. P95 latency dropped from 420ms to 85ms.

Say:

> Same domain, same length. But this has measurements, tool references, and before/after metrics.
> Specificity score: 0.85. The 12+ point gap is demo-safe.

## 2:30 - 3:10: Cross-Track Scanner

Open Scan.

Switch across:

- Content
- Marketplace
- Hiring
- Communications

Say:

> Same engine, different adapters. The universal signals stay constant, while
> each surface gets domain-specific checks.

## 3:10 - 3:50: Batch Similarity

Open Batch.

Click **Score Batch**.

Show duplicate review/cover-letter structures.

Say:

> This is hard to catch item by item. SlopGuard catches the pattern across the
> batch.

## 3:50 - 4:20: Academic Citation Check

Open Citations.

Click **Verify Citations**.

Show likely real vs needs review.

Say:

> The local demo uses citation-shape checks. The production adapter plugs into
> Semantic Scholar, CrossRef, and PubMed.

## 4:20 - 4:50: GitHub Action Demo

Show `apps/action/README.md`:

> SlopGuard ships a native GitHub Action. It runs on every PR, scores the description
> and diff, posts inline annotations on unfalsifiable claims, and creates a check run.

Point out the example PR annotations:

> **SlopGuard: Unfalsifiable Reasoning**
> Add measurement — "it was causing performance issues"? Under what conditions?
> *Specificity: 0.12*

Say:

> This runs automatically on every PR. No setup beyond adding the action to your workflow.

## 4:50 - 5:30: Honest Metrics

Open Metrics.

Click **Run Sample Evaluation**.

Show precision, recall, F1, and confusion matrix.

Say:

> F1 of 0.941 on 104 labeled samples across 9 domains. These are small seed metrics,
> not inflated claims. The README documents where this fails and what needs more data.

## 5:30 - 6:00: Close

Say:

> SlopGuard is the internet's quality layer: passive, explainable, cross-surface
> human oversight scoring. It catches prompt-engineered slop the same way it catches
> genuine low-effort content — by measuring whether reasoning is falsifiable.

## Backup Demos (if judges ask)

### Repo Slop Velocity
Open the Repo tab, show timeline and hotspots.

### Extension
Show the Chrome extension on a GitHub PR page.

### CLI
```bash
python -m slopguard.cli score "Updated files and improved the implementation." --domain code_review
```

### API
```bash
curl -X POST http://localhost:8000/score/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Refactored auth because it was slow.", "domain": "code_review"}'
```
