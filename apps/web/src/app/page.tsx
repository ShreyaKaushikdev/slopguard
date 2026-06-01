import Link from "next/link";

export default function LandingPage() {
  return (
    <>
      {/* Aurora Background */}
      <div className="landing-aurora-bg">
        <div className="landing-aurora-blob landing-blob-1" />
        <div className="landing-aurora-blob landing-blob-2" />
        <div className="landing-aurora-blob landing-blob-3" />
      </div>

      {/* Top Nav */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-nav-brand">SlopGuard</div>
          <div className="landing-nav-links">
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/docs">Docs</Link>
            <Link href="/api-reference">API</Link>
          </div>
          <span className="landing-nav-badge">Hackathon 2026</span>
        </div>
      </nav>

      {/* Main Canvas */}
      <main className="landing-main">

        {/* ── HERO ───────────────────────────────────────────── */}
        <section className="landing-hero">
          <div className="landing-hero-badges">
            <span className="landing-badge landing-badge-teal">
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>science</span>
              F1 = 0.926 on 453 samples
            </span>
            <span className="landing-badge landing-badge-purple">
              <span className="material-symbols-outlined" style={{ fontSize: 14 }}>radar</span>
              10 Universal Signals
            </span>
          </div>
          <h1 className="landing-hero-title">The Internet&rsquo;s<br/>Quality Layer</h1>
          <p className="landing-hero-subtitle">
            Scores content for human oversight quality &mdash; not AI authorship.
            10 signals including 3 novel detectors nobody else built.
          </p>
          <div className="landing-hero-ctas">
            <Link href="/dashboard" className="landing-btn-primary">
              Open Dashboard
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>arrow_forward</span>
            </Link>
            <a href="https://github.com" target="_blank" rel="noreferrer" className="landing-btn-secondary">
              View on GitHub
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>code</span>
            </a>
          </div>
        </section>

        {/* ── PROBLEM ────────────────────────────────────────── */}
        <section className="landing-section-grid">
          <div className="landing-section-label-col">
            <span className="landing-section-num">01 / The Problem</span>
            <h2 className="landing-section-heading">Erosion of Trust</h2>
          </div>
          <div className="landing-glass-panel landing-section-content-col">
            <blockquote className="landing-blockquote">
              &ldquo;Slop was the 2025 Word of the Year.&rdquo;
            </blockquote>
            <p className="landing-body-text">
              Generation is cheap, but evaluation remains expensive. As synthetic content floods
              digital spaces, human attention is consumed filtering out low-effort text.
              The PR descriptions get vaguer. The docs get more circular. The reviews get less trustworthy.
              One day you realise you don&rsquo;t trust any of it, and you can&rsquo;t point to when it changed.
              That&rsquo;s what slop does. Not destruction. <em>Erosion.</em>
            </p>
          </div>
        </section>

        {/* ── HOW IT WORKS ──────────────────────────────────── */}
        <section className="landing-section">
          <span className="landing-section-num">02 / How It Works</span>
          <h2 className="landing-section-heading">The Analysis Pipeline</h2>
          <div className="landing-steps-grid">
            <div className="landing-glass-panel landing-step-card">
              <div className="landing-step-icon">
                <span className="material-symbols-outlined" style={{ fontSize: 32 }}>content_paste</span>
              </div>
              <h3 className="landing-step-title">1. Paste Content</h3>
              <p className="landing-step-desc">Input text from any source &mdash; PRs, docs, articles, reviews.</p>
            </div>
            <div className="landing-glass-panel landing-step-card">
              <div className="landing-step-icon landing-step-icon-purple">
                <span className="material-symbols-outlined" style={{ fontSize: 32 }}>memory</span>
              </div>
              <h3 className="landing-step-title">2. 10 Signals Analyze</h3>
              <p className="landing-step-desc">Deep-ensemble evaluates structural, semantic, and epistemic quality.</p>
            </div>
            <div className="landing-glass-panel landing-step-card landing-step-card-score">
              <div className="landing-score-ring">
                <svg viewBox="0 0 100 100">
                  <circle className="landing-ring-track" cx="50" cy="50" r="40" />
                  <circle className="landing-ring-fill" cx="50" cy="50" r="40" strokeDasharray="251.2" strokeDashoffset="70.336" />
                </svg>
                <span className="landing-score-number">72</span>
              </div>
              <h3 className="landing-step-title">3. Get Score</h3>
              <p className="landing-step-desc">0&ndash;100 quality index with full signal breakdown.</p>
              <span className="landing-badge landing-badge-purple" style={{ marginTop: 8 }}>Mixed Quality</span>
            </div>
          </div>
        </section>

        {/* ── 8 TRACKS ──────────────────────────────────────── */}
        <section className="landing-section">
          <span className="landing-section-num">03 / 8 Domain Tracks</span>
          <h2 className="landing-section-heading">Universal Application</h2>
          <div className="landing-tracks-grid">
            {[
              { letter: "A", name: "Code Review",     desc: "Detecting automated boilerplate and missing rationale in PRs." },
              { letter: "B", name: "Docs & KBs",      desc: "Filtering out hallucinated procedures and circular logic." },
              { letter: "C", name: "Hiring",           desc: "Identifying mass-generated cover letters and generic responses." },
              { letter: "D", name: "Communications",   desc: "Scoring internal updates for clarity over verbosity." },
              { letter: "E", name: "Content & SEO",    desc: "Flagging zero-value informational rehashes." },
              { letter: "F", name: "Academia",         desc: "Detecting structural mimicry in peer reviews and abstracts." },
              { letter: "G", name: "Marketplaces",     desc: "Weeding out synthetic reviews and automated product descriptions." },
              { letter: "H", name: "Social & News",    desc: "Identifying engagement-bait narratives and synthetic outrage." },
            ].map((track) => (
              <div key={track.letter} className={`landing-glass-panel landing-track-card${track.letter === "A" ? " landing-track-active" : ""}`}>
                <span className="landing-track-letter">Track {track.letter}</span>
                <h3 className="landing-track-name">{track.name}</h3>
                <p className="landing-track-desc">{track.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── NOVEL SIGNALS ─────────────────────────────────── */}
        <section className="landing-section">
          <span className="landing-section-num">04 / 3 Novel Signals</span>
          <h2 className="landing-section-heading">Sharpest Signal Prize</h2>
          <p className="landing-body-text" style={{ maxWidth: 720, marginBottom: 40 }}>
            Three novel detection signals that nobody else has thought of. They&rsquo;re technically
            sophisticated, hard to fake, and catch patterns invisible to traditional detectors.
          </p>
          <div className="landing-signals-grid">
            <div className="landing-glass-panel landing-signal-card">
              <div className="landing-signal-icon">
                <span className="material-symbols-outlined" style={{ fontSize: 32 }}>shield</span>
              </div>
              <h3 className="landing-signal-title">Epistemic Cowardice</h3>
              <p className="landing-signal-desc">
                Detects systematic avoidance of taking positions &mdash; hedge clustering,
                false balance, opinion laundering. AI hedges everything; humans commit.
              </p>
              <span className="landing-badge landing-badge-gold">Weight: 1.5</span>
            </div>
            <div className="landing-glass-panel landing-signal-card">
              <div className="landing-signal-icon landing-signal-icon-blue">
                <span className="material-symbols-outlined" style={{ fontSize: 32 }}>alt_route</span>
              </div>
              <h3 className="landing-signal-title">Counterfactual Absence</h3>
              <p className="landing-signal-desc">
                Detects missing alternatives, failure modes, and tradeoffs.
                AI generates the happy path; humans think about what breaks.
              </p>
              <span className="landing-badge landing-badge-gold">Weight: 1.8</span>
            </div>
            <div className="landing-glass-panel landing-signal-card">
              <div className="landing-signal-icon landing-signal-icon-purple">
                <span className="material-symbols-outlined" style={{ fontSize: 32 }}>show_chart</span>
              </div>
              <h3 className="landing-signal-title">Vocabulary Novelty</h3>
              <p className="landing-signal-desc">
                Analyzes the <strong>SHAPE</strong> of vocabulary introduction over time.
                Human: declining curve with spikes. AI: flat uniform line.
              </p>
              <span className="landing-badge landing-badge-gold">Weight: 1.6</span>
            </div>
          </div>
        </section>

        {/* ── METRICS ───────────────────────────────────────── */}
        <section className="landing-section">
          <span className="landing-section-num">05 / Honest Numbers</span>
          <h2 className="landing-section-heading">Verified Performance</h2>
          <div className="landing-metrics-grid">
            <div className="landing-glass-panel landing-metric-card">
              <span className="landing-metric-value landing-metric-teal">0.926</span>
              <span className="landing-metric-label">F1 Score</span>
            </div>
            <div className="landing-glass-panel landing-metric-card">
              <span className="landing-metric-value landing-metric-blue">0.887</span>
              <span className="landing-metric-label">Precision</span>
            </div>
            <div className="landing-glass-panel landing-metric-card">
              <span className="landing-metric-value landing-metric-purple">0.969</span>
              <span className="landing-metric-label">Recall</span>
            </div>
            <div className="landing-glass-panel landing-metric-card">
              <span className="landing-metric-value landing-metric-gold">453</span>
              <span className="landing-metric-label">Total Samples</span>
            </div>
          </div>
          <p className="landing-body-text" style={{ textAlign: "center", marginTop: 24, maxWidth: 640, marginLeft: "auto", marginRight: "auto" }}>
            Evaluated across 453 multi-source samples. Hand-labeled seed, real GitHub PRs
            from 15 repos, arXiv, Reddit, and live ingestion data. Domain-calibrated thresholds.
          </p>
        </section>

        {/* ── CTA BANNER ────────────────────────────────────── */}
        <section className="landing-cta-section">
          <div className="landing-glass-panel landing-cta-card">
            <h2 className="landing-cta-title">Ready to scan?</h2>
            <p className="landing-body-text" style={{ textAlign: "center", maxWidth: 500, marginBottom: 32 }}>
              Paste any text and see exactly which signals fire. Catch what people can&rsquo;t &mdash;
              or won&rsquo;t &mdash; catch on their own.
            </p>
            <Link href="/dashboard" className="landing-btn-primary landing-btn-lg">
              Open Dashboard
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_forward</span>
            </Link>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-brand">
            <strong>SlopGuard</strong>
            <span>Built for Slop Scan Hackathon 2026 · Track A &mdash; Code Review</span>
            <span>&copy; 2026 SlopGuard. Shielding the frontier.</span>
          </div>
          <div className="landing-footer-links">
            <span className="landing-footer-links-title">Links</span>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/docs">Documentation</Link>
            <Link href="/api-reference">API Reference</Link>
            <a href="https://github.com" target="_blank" rel="noreferrer">GitHub</a>
          </div>
        </div>
      </footer>
    </>
  );
}
