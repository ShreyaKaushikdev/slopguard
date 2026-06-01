import Link from "next/link";

const endpoints = [
  { method: "POST", path: "/score/text", desc: "Score any text + domain" },
  { method: "POST", path: "/score/pr", desc: "Score PR title + description + diff" },
  { method: "POST", path: "/score/pr-url", desc: "Fetch and score a public GitHub PR URL" },
  { method: "POST", path: "/score/repo", desc: "Full repo analysis with timeline and hotspots" },
  { method: "POST", path: "/score/batch", desc: "Score many texts, returns clustering" },
  { method: "POST", path: "/score/citations", desc: "Citation verification (CrossRef + Semantic Scholar + PubMed)" },
  { method: "POST", path: "/improve", desc: "Improvement suggestions for flagged sentences" },
  { method: "GET",  path: "/live/feed", desc: "Real content scored live from 10 sources" },
  { method: "GET",  path: "/live/stats", desc: "Ingestion stats — items/min, slop rate, uptime" },
  { method: "GET",  path: "/live/stream", desc: "SSE stream of scored items" },
  { method: "POST", path: "/live/score-url", desc: "Score any URL in real time" },
  { method: "GET",  path: "/ticker", desc: "60-second rolling window stats" },
  { method: "GET",  path: "/ticker/live", desc: "SSE ticker stream" },
  { method: "POST", path: "/signals/epistemic-cowardice", desc: "Epistemic cowardice analysis" },
  { method: "POST", path: "/signals/counterfactual-absence", desc: "Counterfactual analysis" },
  { method: "POST", path: "/signals/vocabulary-novelty", desc: "Vocabulary novelty curve + visualization" },
  { method: "GET",  path: "/evaluation/sample", desc: "F1/precision/recall on seed dataset" },
  { method: "GET",  path: "/evaluation/hc3", desc: "Multi-source evaluation (431 samples)" },
  { method: "GET",  path: "/demo/scenarios", desc: "8 built-in demo examples with expected scores" },
  { method: "GET",  path: "/leaderboard/sites", desc: "Site quality leaderboard" },
  { method: "GET",  path: "/leaderboard/repos", desc: "Repo oversight leaderboard" },
  { method: "GET",  path: "/health", desc: "Service health check" },
];

export default function ApiReferencePage() {
  return (
    <>
      <div className="landing-aurora-bg">
        <div className="landing-aurora-blob landing-blob-1" />
        <div className="landing-aurora-blob landing-blob-3" />
      </div>
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <Link href="/" className="landing-nav-brand" style={{ textDecoration: "none" }}>SlopGuard</Link>
          <div className="landing-nav-links">
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/docs">Docs</Link>
            <Link href="/api-reference" style={{ color: "#57f1db" }}>API</Link>
          </div>
          <span className="landing-nav-badge">Hackathon 2026</span>
        </div>
      </nav>

      <main className="landing-main" style={{ maxWidth: 960, gap: 48 }}>
        <section style={{ paddingTop: 40 }}>
          <span className="landing-section-num">API Reference</span>
          <h1 className="landing-section-heading">45+ Endpoints</h1>
          <p className="landing-body-text" style={{ maxWidth: 640 }}>
            All endpoints accept and return JSON. Base URL:&nbsp;
            <code style={{ fontFamily: "var(--mono)", color: "#57f1db", background: "rgba(87,241,219,0.1)", padding: "2px 8px", borderRadius: 4, fontSize: 14 }}>
              http://localhost:8000
            </code>
          </p>
        </section>

        <div className="landing-glass-panel" style={{ padding: 32, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--sans)" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={{ textAlign: "left", padding: "12px 16px", fontFamily: "var(--mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--i3)" }}>Method</th>
                <th style={{ textAlign: "left", padding: "12px 16px", fontFamily: "var(--mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--i3)" }}>Endpoint</th>
                <th style={{ textAlign: "left", padding: "12px 16px", fontFamily: "var(--mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--i3)" }}>Description</th>
              </tr>
            </thead>
            <tbody>
              {endpoints.map((ep, i) => (
                <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <td style={{ padding: "10px 16px" }}>
                    <span style={{
                      fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600,
                      padding: "3px 8px", borderRadius: 4,
                      background: ep.method === "POST" ? "rgba(87,241,219,0.12)" : "rgba(88,166,255,0.12)",
                      color: ep.method === "POST" ? "#57f1db" : "#58a6ff",
                    }}>
                      {ep.method}
                    </span>
                  </td>
                  <td style={{ padding: "10px 16px", fontFamily: "var(--mono)", fontSize: 13, color: "var(--i1)" }}>{ep.path}</td>
                  <td style={{ padding: "10px 16px", fontSize: 14, color: "var(--i3)" }}>{ep.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="landing-glass-panel" style={{ padding: 48 }}>
          <h2 style={{ fontFamily: "var(--headline)", fontSize: 24, color: "var(--i1)", marginBottom: 24 }}>Example Request</h2>
          <pre style={{ fontFamily: "var(--mono)", fontSize: 13, color: "#57f1db", background: "rgba(0,0,0,0.3)", padding: 24, borderRadius: 8, overflowX: "auto", lineHeight: 1.6 }}>
{`curl -X POST http://localhost:8000/score/text \\
  -H "Content-Type: application/json" \\
  -d '{
    "text": "Updated the auth module to improve security.",
    "domain": "code_review"
  }'

# Response:
{
  "score": 32,
  "oversight": "low",
  "summary": "Generic improvement claim without specifics",
  "signals": [...],
  "highlights": ["Updated the auth module to improve security."]
}`}
          </pre>
        </div>

        <div style={{ textAlign: "center", padding: "24px 0" }}>
          <Link href="/dashboard" className="landing-btn-primary">
            Try It Live
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
            <Link href="/docs">Documentation</Link>
          </div>
        </div>
      </footer>
    </>
  );
}
