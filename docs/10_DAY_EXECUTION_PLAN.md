# SlopGuard 10-Day Execution Plan

This plan keeps the full SlopGuard vision: browser extension + API + dashboard
covering all 8 Slop Scan tracks. The trick is to ship a unified engine first,
then make every track feel real through a domain adapter, sample data, and one
demo-ready workflow.

## Day 1: Repo, API, and Extension Skeleton

- Finalize monorepo structure.
- Ship FastAPI `/score/text`, `/score/pr`, `/score/batch`.
- Ship Chrome extension overlay for generic pages and GitHub.
- Add PRD, README, and sample data.

Exit criteria:

- API tests pass.
- Extension can call local API.
- Dashboard builds.

## Day 2: Universal Detection Engine

- Improve information density scoring.
- Add sentence-level highlight output.
- Add WHY vs WHAT classifier v1.
- Add concrete detail and template structure scoring.
- Create 80 labeled samples across reviewed/slop categories.

Exit criteria:

- Every score includes explainable reasons.
- Bad generic text scores lower than specific reviewed text.

## Day 3: Track A Code Review

- Add GitHub PR page extraction in extension.
- Add diff paste field in dashboard.
- Implement PR diff divergence.
- Implement rubber-stamp review comment proxy.
- Add 10 real PR examples for demo.

Exit criteria:

- Demo can score a PR description against a diff.

## Day 4: Tracks B, D, and E

- Docs: heading-to-content ratio and example density.
- Communications: decision/action density and compression proxy.
- Content/SEO: claim specificity and time-to-value.
- Add dashboard tabs for these tracks.

Exit criteria:

- Same engine visibly adapts to docs, comms, and article content.

## Day 5: Tracks C and G Batch Detection

- Batch upload UI for cover letters/reviews.
- Structural fingerprint clustering.
- Repeated opening and sentence-shape warnings.
- Add review specificity and achievement specificity signals.

Exit criteria:

- Demo can upload 10-20 samples and show suspicious clusters.

## Day 6: Tracks F and H

- Academia: citation extraction and verification status states.
- Social/news: rage-bait fingerprint and source-reference balance.
- Add placeholder external adapter interfaces for CrossRef/Semantic Scholar.

Exit criteria:

- All 8 tracks have visible adapters with explainable scoring.

## Day 7: Slop Velocity and Leaderboards

- Build repo/site leaderboard pages.
- Add mock Slop Velocity Timeline from sample data.
- Add repo score history shape to API.
- Polish dashboard visuals.

Exit criteria:

- The "internet quality layer" story is visible, not just described.

## Day 8: Evaluation Harness

- Create labeled benchmark JSON.
- Add script to compute precision, recall, F1, and confusion matrix.
- Document failure cases honestly.
- Tune thresholds.

Exit criteria:

- README has real numbers, not vibes.

## Day 9: Open Source Ready

- Add contribution guide.
- Add issue templates.
- Add GitHub Actions for API tests and web build.
- Add `.env.example`.
- Add screenshots/GIF placeholders.

Exit criteria:

- Repo feels installable and judge-friendly.

## Day 10: Demo Lock

- Record 2-3 minute video.
- Prepare 5-minute live demo script.
- Freeze sample inputs.
- Test extension install from scratch.
- Test API + dashboard startup from README only.

Exit criteria:

- A judge can clone, run, and understand SlopGuard in under 5 minutes.

## Team Ownership

| Owner | Focus |
| --- | --- |
| Urjit (solo) | architecture, all adapters, dashboard, extension, demo |

## Demo Rule

Every feature shown in the demo must answer one sentence:

> Did a human actually think about this before publishing?

