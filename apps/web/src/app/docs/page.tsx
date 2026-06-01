import Link from "next/link";

export default function DocsPage() {
  return (
    <>
      <div className="landing-aurora-bg">
        <div className="landing-aurora-blob landing-blob-1" />
        <div className="landing-aurora-blob landing-blob-2" />
      </div>
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <Link href="/" className="landing-nav-brand" style={{ textDecoration: "none" }}>SlopGuard</Link>
          <div className="landing-nav-links">
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/docs" style={{ color: "#57f1db" }}>Docs</Link>
            <Link href="/api-reference">API</Link>
          </div>
          <span className="landing-nav-badge">Hackathon 2026</span>
        </div>
      </nav>

      <main className="landing-main" style={{ maxWidth: 900, gap: 48 }}>
        <section style={{ paddingTop: 40 }}>
          <span className="landing-section-num">Documentation</span>
          <h1 className="landing-section-heading">Getting Started with SlopGuard</h1>
        </section>

        <div className="landing-glass-panel" style={{ padding: 48 }}>
          <h2 style={{ fontFamily: "var(--headline)", fontSize: 24, color: "var(--i1)", marginBottom: 24 }}>Quick Start</h2>
          <pre style={{ fontFamily: "var(--mono)", fontSize: 14, color: "#57f1db", background: "rgba(0,0,0,0.3)", padding: 24, borderRadius: 8, overflowX: "auto", lineHeight: 1.6 }}>
{`# Clone the repo
git clone https://github.com/your-org/slopguard.git
cd slopguard

# Start the API
cd apps/api
pip install -r requirements.txt
uvicorn slopguard.main:app --reload --port 8000

# Start the Dashboard
cd apps/web
npm install && npm run dev`}
          </pre>
        </div>

        <div className="landing-glass-panel" style={{ padding: 48 }}>
          <h2 style={{ fontFamily: "var(--headline)", fontSize: 24, color: "var(--i1)", marginBottom: 24 }}>Detection Engine</h2>
          <p className="landing-body-text" style={{ marginBottom: 16 }}>
            SlopGuard uses <strong style={{ color: "#57f1db" }}>10 universal signals</strong> to evaluate every piece of content:
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              "Information Density", "Causal Reasoning (Why vs What)",
              "Specificity", "Semantic Uniqueness",
              "Template Structure", "Human Delta",
              "Evidence Density", "⭐ Epistemic Cowardice",
              "⭐ Counterfactual Absence", "⭐ Vocabulary Novelty",
            ].map((s) => (
              <div key={s} style={{ fontFamily: "var(--mono)", fontSize: 13, color: s.startsWith("⭐") ? "#57f1db" : "var(--i3)", padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 6, border: "1px solid rgba(255,255,255,0.06)" }}>
                {s}
              </div>
            ))}
          </div>
        </div>

        <div className="landing-glass-panel" style={{ padding: 48 }}>
          <h2 style={{ fontFamily: "var(--headline)", fontSize: 24, color: "var(--i1)", marginBottom: 24 }}>8 Domain Tracks</h2>
          <p className="landing-body-text">
            SlopGuard covers all 8 hackathon tracks with domain-specific adapters:
            Code Review, Docs &amp; KBs, Hiring, Communications, Content &amp; SEO,
            Academia, Marketplaces, and Social &amp; News. Each domain uses calibrated
            thresholds and specialized signal weights.
          </p>
        </div>

        <div style={{ textAlign: "center", padding: "24px 0" }}>
          <Link href="/dashboard" className="landing-btn-primary">
            Open Dashboard
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
          </Link>
        </div>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-brand">
            <strong>SlopGuard</strong>
            <span>Built for Slop Scan Hackathon 2026</span>
          </div>
          <div className="landing-footer-links">
            <span className="landing-footer-links-title">Links</span>
            <Link href="/">Home</Link>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/api-reference">API Reference</Link>
          </div>
        </div>
      </footer>
    </>
  );
}
