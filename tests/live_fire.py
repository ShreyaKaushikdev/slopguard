#!/usr/bin/env python
"""Live-Fire Testing — Real World Content Against SlopGuard."""
import sys, json, os
project_root = os.path.join(os.path.dirname(__file__), "..", "apps", "api")
sys.path.insert(0, os.path.normpath(project_root))

from slopguard.scoring import score_text
from slopguard.detectors.specificity import ai_slop_fingerprint
from slopguard.detectors.improvement import improve_text

def show(name, result, expected_lo, expected_hi):
    status = "OK" if expected_lo <= result.score <= expected_hi else "FAIL"
    print(f"  [{status}] {name}: score={result.score}, oversight={result.oversight}")

# === TRACK A: Code Review ===
print("\n=== TRACK A: Code Review ===")

linus_pr = """pull request: networking fixes

The following changes since commit abc123:

  commit abc123def456
  Author: David Miller <davem@davemloft.net>

      net: fix use-after-free in tcp_rcv_established()

      syzbot reported a use-after-free in tcp_rcv_established() when
      a socket is freed while a timer is still pending. The bug is
      triggered when tcp_done() is called from tcp_v4_rcv() without
      first cancelling the keepalive timer.

      Fix by calling inet_csk_clear_xmit_timer() before tcp_done().
      Tested with 10,000 iterations of the syzbot reproducer.
"""
r = score_text(linus_pr, "code_review")
show("Linus PR (syzbot UAF fix)", r, 63, 85)

copilot_pr = """Update the codebase to improve functionality

This pull request updates the existing implementation to provide better
performance and reliability. The changes address various issues and
enhance the overall code quality.

Key improvements:
- Improved error handling
- Better code organization
- Enhanced readability
- Fixed various bugs
"""
r = score_text(copilot_pr, "code_review")
show("Copilot PR (generic)", r, 25, 45)

good_pr = """Replace blocking DNS resolution with async resolver in http_client.go

Our HTTP client was using net.DefaultResolver which blocks the goroutine
for the full DNS timeout (5s default) when a nameserver is unreachable.
During the May 15 incident, this caused 847 goroutine leaks across
our API servers when the internal DNS server (10.0.1.53) became unreachable.

Changes:
- Added custom resolver with 500ms timeout (down from 5s)
- Implemented fallback to secondary DNS (10.0.1.54) on timeout

Before: 5s blocking per failed lookup, goroutine count grew to 12,000
After: 500ms timeout, goroutine count stable at 340 under same conditions

Tested with load test: 50K requests/min with DNS server down, latency P99 at 520ms (vs 5.2s before).
"""
r = score_text(good_pr, "code_review")
show("High-quality PR (async DNS)", r, 60, 85)

fake_pr = """Optimize the database query layer for improved performance

Our database queries were causing latency issues in production because
the query planner was not efficiently using indexes for complex JOIN
operations. I analyzed the EXPLAIN output and found that the users table
scan was taking 240ms on average.

Changes:
- Added composite index on users(email, status) to reduce scan time
- Refactored the ORDER BY clause to use the covering index

The query time improved significantly after these changes, and the
database CPU utilization dropped from 78 percent to a more reasonable level.
"""
r = score_text(fake_pr, "code_review")
show("Fake-specific PR (looks technical but vague)", r, 35, 53)

# === TRACK C: Hiring ===
print("\n=== TRACK C: Hiring ===")

prompt_cover = """Dear Hiring Manager,

I am writing to express my strong interest in the Senior Software Engineer
position at Stripe. During my 3 years at Shopify, I led the migration of
our payment processing system from a monolithic Ruby on Rails architecture
to a microservices-based Go platform, which reduced API latency by 42 percent
(from 180ms to 105ms P95) and decreased infrastructure costs by 240,000 dollars
annually.

I was particularly drawn to Stripe because of your work on Stripe Connect,
which I studied extensively while building a marketplace platform for my
previous startup.

At Shopify, I also:
- Mentored 4 junior engineers, 3 of whom were promoted within 18 months
- Reduced CI/CD pipeline time from 45 minutes to 12 minutes
- Led the incident response for the Black Friday 2024 outage, coordinating
  across 3 teams to restore service within 23 minutes

I am excited about the opportunity to bring my experience in distributed
systems and payment processing to Stripe.
"""
r = score_text(prompt_cover, "hiring")
show("GPT-4 prompt-eng cover letter", r, 48, 65)
why = next((s for s in r.signals if s.name == "why_vs_what"), None)
if why:
    print(f"       specificity={why.specificity_score}, flagged={len(why.flagged_claims)}")

human_cover = """Hi Stripe recruiting team,

Saw your posting for the Senior SWE role on HN. Ive been at Shopify for
about 3 years now, mostly working on the payments team. We moved our core
payment processing from Rails to Go last year - I was the one who wrote
the migration plan and did most of the heavy lifting on the Go side.

The main thing Im proud of: our P95 latency went from 180ms down to
around 100ms after the migration. Not exactly sure on the exact number
anymore but definitely under 110ms. We also saved a bunch on infra costs.

Also led the Black Friday incident response last year when our payment
processor went down for like 20 minutes. Anyway, would love to chat.
"""
r = score_text(human_cover, "hiring")
show("Real human cover letter (messy)", r, 55, 75)

# === TRACK E: Content ===
print("\n=== TRACK E: Content ===")

seo = """In todays fast-paced digital landscape, productivity has become more
important than ever. Whether youre a seasoned professional or just starting
your career, the right tools can make all the difference in unlocking your
full potential.

In this comprehensive guide, we will explore the various aspects of modern
productivity and how they can transform your workflow. From time management
to task organization, we will delve into the best practices that industry
experts recommend.
"""
r = score_text(seo, "content")
show("SEO filler article", r, 20, 40)
fp = ai_slop_fingerprint(seo)
print(f"       ai_slop={fp['slop_score']}, patterns={fp['total_signals']}")

real_article = """The CVE-2024-3094 vulnerability in xz-utils versions 5.6.0 and 5.6.1
was one of the most sophisticated supply chain attacks ever discovered.
The malicious code was inserted into the xz/liblzma build system via a
backdoor in the test files, which executed during the autotools build process.

The backdoor modified the liblzma binary to intercept SSH authentication
in systemd-logind. Specifically, it hooked into the RSA key verification
at offset 0x4a7c of the compiled binary.

Andres Freund discovered the anomaly when he noticed sshd was using
2-3ms more CPU time than expected - a difference he caught because he
had been benchmarking Debian SSH performance for a PostgreSQL mailing list.
"""
r = score_text(real_article, "content")
show("Real article (CVE-2024-3094)", r, 60, 85)

# === TRACK G: Marketplace ===
print("\n=== TRACK G: Marketplace ===")

fake_reviews = [
    "Amazing product! Great quality and highly recommend. Works perfectly and exceeded my expectations.",
    "Excellent product! Very good quality and I highly recommend it. Works great and exceeded all expectations.",
    "Wonderful product! Awesome quality and definitely recommend. Works fantastic and surpassed expectations.",
]
for i, rev in enumerate(fake_reviews, 1):
    r = score_text(rev, "marketplace")
    show(f"Fake review #{i}", r, 20, 40)

real_review = """I bought this USB-C hub for my M2 MacBook Pro. The HDMI port works
fine with my Dell 27 inch monitor at 4K 60Hz. The SD card reader is slow
though - copying a 4GB video file took about 90 seconds. The USB-A ports
work fine with my keyboard and mouse.

One issue: the hub gets warm after about 30 minutes of use. Not hot enough
to be concerning but noticeable. For 35 dollars its decent. The Anker one
at 55 dollars is probably better build quality but I did not need extra ports.
"""
r = score_text(real_review, "marketplace")
show("Real authentic review", r, 60, 85)

# === TRACK H: Social ===
print("\n=== TRACK H: Social/News ===")

rage = """BREAKING: Tech company FIRES employee for using AI to do his job!
The company said he was unproductive but his manager admitted he was
meeting ALL his deadlines. This is what happens when corporations want
to SCREW workers! SHARE if you think this is WRONG!"""
r = score_text(rage, "social_news")
show("Rage bait", r, 20, 40)

# === TRACK B: Docs ===
print("\n=== TRACK B: Docs ===")

circular = """Authentication is the process of authenticating users. When a user needs
to authenticate, the system performs authentication to verify the users
identity. The authentication module handles authentication requests by
calling the authentication service, which authenticates the user against
the authentication database.
"""
r = score_text(circular, "docs")
show("Circular documentation", r, 20, 47)

good_doc = """Users authenticate by providing an email and password to POST /api/v1/auth/login.
The server validates the password against the bcrypt hash stored in the users
table. On success, returns a JWT valid for 24 hours.

Rate limiting: 5 failed attempts per IP per 15 minutes. After 5 failures,
the IP is blocked for 30 minutes and a 429 response is returned.
"""
r = score_text(good_doc, "docs")
show("Good documentation", r, 60, 85)

# === TRACK D: Communications ===
print("\n=== TRACK D: Communications ===")

slack_slop = """Hey team, just wanted to give a quick update on the project. We have
made some progress on various fronts and there are a few things to note.
Overall things are moving in the right direction. Let me know if anyone
has questions or concerns. Thanks!"""
r = score_text(slack_slop, "communications")
show("Slack slop (zero info)", r, 20, 40)

good_comms = """Update on the payment migration:

1. Completed: 847 of 1,200 user accounts migrated
2. Blocked: 23 accounts have duplicate payment methods - need manual review
   (list in #payments-migration, pinned comment)
3. Risk: The Stripe webhook for subscription renewals has not been tested
   with the new API yet. @sarah can you verify by EOD?

Timeline: On track for Friday 3pm deploy.
"""
r = score_text(good_comms, "communications")
show("Good communication", r, 55, 85)

# === IMPROVEMENT ENGINE TEST ===
print("\n=== IMPROVEMENT ENGINE (20 tests) ===")

test_inputs = [
    ("code_review", "Updated the auth flow because it was slow and needed better security."),
    ("code_review", "Improved database performance by optimizing queries."),
    ("code_review", "Refactored the API to handle more requests."),
    ("code_review", "Fixed various issues in the billing module."),
    ("code_review", "Made changes to several files to improve the overall experience."),
    ("docs", "Updated the documentation for various endpoints."),
    ("code_review", "The new implementation is more robust and reliable."),
    ("content", "This is a better approach that provides improved results."),
    ("code_review", "Enhanced the user experience with a cleaner design."),
    ("code_review", "Changed the timeout because it could potentially reduce errors in some cases."),
    ("code_review", "Updated the cache settings since it might improve response times for certain users."),
    ("content", "In todays digital landscape, various tools play a crucial role in helping teams."),
    ("code_review", "Refactored the service layer to provide better error handling for various edge cases."),
    ("content", "This comprehensive guide delves into the rich ecosystem of modern development."),
    ("content", "Whether youre a seasoned developer or just starting, this robust solution will empower your workflow."),
    ("code_review", "Improved the authentication module because it was causing performance issues."),
    ("hiring", "I led various initiatives that significantly improved team productivity."),
    ("marketplace", "Great product with amazing quality that exceeded my expectations and I highly recommend it."),
    ("academia", "Our approach demonstrates significant improvements over baseline methods in various settings."),
    ("communications", "Made progress on multiple fronts and things are looking good for the deadline."),
]

imp_pass = 0
imp_fail = 0

for i, (domain, text) in enumerate(test_inputs, 1):
    result = improve_text(text, domain)
    suggestions = result.get("suggestions", [])

    if not suggestions:
        print(f"  [WARN] #{i}: No suggestions for: {text[:50]}...")
        imp_fail += 1
        continue

    s = suggestions[0]
    suggestion = s.get("suggestion", {})
    example = suggestion.get("example", "")
    questions = suggestion.get("questions", [])
    issue = suggestion.get("issue", "unknown")

    has_specific = any("?" in q and len(q) > 15 for q in questions)
    has_concrete = len(example) > 30

    if has_specific or has_concrete:
        print(f"  [OK] #{i}: {issue[:50]}")
        imp_pass += 1
    else:
        print(f"  [FAIL] #{i}: Vague - example='{example[:50]}'")
        imp_fail += 1

print(f"\nImprovement Engine: {imp_pass} pass, {imp_fail} fail out of {len(test_inputs)}")
