from slopguard.scoring import score_text

tests = [
    ("AI hedge", "This approach may have performance implications depending on your use case. It could potentially work well in some scenarios. Results may vary.", "code_review"),
    ("Human position", "Don't use this pattern. We tried it on payments and it caused a 3x increase in DB connections. Pool exhausted at 400 users. Use repository pattern instead.", "code_review"),
    ("AI happy path", "Implemented caching using Redis. Performance is improved. The implementation follows best practices.", "code_review"),
    ("Human counterfactual", "Added Redis caching. Considered Memcached but rejected it because we need pub/sub for cache invalidation. TTL 300s shorter hammers DB, longer risks stale data. Known limitation: no invalidation on admin edits. Accepted that risk.", "code_review"),
    ("SEO slop", "In today's digital landscape, leveraging cutting-edge solutions is crucial. This comprehensive guide explores best practices to unlock your potential.", "content"),
    ("Real article", "PostgreSQL 16 incremental backup cut our 1.2TB backup window from 4 hours to 90 minutes. Tested on AWS RDS with pg_basebackup. Limitation: requires WAL archiving enabled.", "content"),
]

print(f"{'Content':<25} {'Score':>6} {'Label':>8} | EC     CF     VN")
print("-" * 70)
for name, text, domain in tests:
    r = score_text(text, domain)
    sigs = {s.name: s.score for s in r.signals}
    ec = sigs.get("epistemic_cowardice", 0)
    cf = sigs.get("counterfactual_absence", 0)
    vn = sigs.get("vocabulary_novelty", 0)
    print(f"{name:<25} {r.score:>6.1f} {r.oversight:>8} | {ec:.3f}  {cf:.3f}  {vn:.3f}")
