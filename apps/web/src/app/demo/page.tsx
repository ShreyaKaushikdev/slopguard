"use client";

import { useState } from "react";
import VocabularyNoveltyCurve from "../../components/VocabularyNoveltyCurve";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AnalysisResult = {
  score: number;
  signals: {
    name: string;
    score: number;
    weight: number;
    reason: string;
    detail: string;
  }[];
};

export default function DemoPage() {
  const [loading1, setLoading1] = useState(false);
  const [res1a, setRes1a] = useState<AnalysisResult | null>(null);
  const [res1b, setRes1b] = useState<AnalysisResult | null>(null);

  const [loading2, setLoading2] = useState(false);
  const [res2a, setRes2a] = useState<AnalysisResult | null>(null);
  const [res2b, setRes2b] = useState<AnalysisResult | null>(null);

  const [text3a] = useState("Refactored the authentication module because it was causing performance issues in production. The new implementation is more robust and provides better error handling for various edge cases. The refactoring addresses core technical debt and streamlines the implementation significantly. Extensive testing has been performed to guarantee optimal functionality across all supported devices and browsers. Security vulnerabilities have been meticulously mitigated through the implementation of advanced encryption algorithms. The system architecture has been fundamentally optimized to handle increased load without compromising overall performance. Furthermore, code maintainability is greatly improved by strictly adhering to modern linting guidelines. Documentation has been thoroughly updated to clearly reflect the new API endpoints. We anticipate this will significantly reduce the number of ongoing support tickets related to login issues.");
  const [text3b] = useState("Changed billing/retry.ts to cap retries at 3 because Stripe was returning duplicate webhook delivery during deploys. Added a 10-minute idempotency window and tested with the replay fixture. Considered exponential backoff but rejected it because our SLA requires retry within 30s. Tradeoff: slower recovery on transient failures, but eliminates double-billing risk. Known limitation: if Secrets Manager API is unavailable during deploy, auth fails completely. Accepted this risk, added monitoring alert.");

  async function scoreSection1() {
    setLoading1(true);
    try {
      const [a, b] = await Promise.all([
        fetch(`${API_URL}/score/text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            text: "We might want to update the database query because it could potentially improve performance for some users in certain scenarios.", 
            domain: "code_review" 
          })
        }).then(r => r.json()),
        fetch(`${API_URL}/score/text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            text: "Update the users query to add a composite index on (org_id, created_at). Profiling showed full table scans causing 800ms latency on the dashboard. This will bring latency under 50ms.", 
            domain: "code_review" 
          })
        }).then(r => r.json())
      ]);
      setRes1a(a);
      setRes1b(b);
    } finally {
      setLoading1(false);
    }
  }

  async function scoreSection2() {
    setLoading2(true);
    try {
      const [a, b] = await Promise.all([
        fetch(`${API_URL}/score/text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            text: "Implemented the new payment flow as requested. It works great and all tests pass.", 
            domain: "code_review" 
          })
        }).then(r => r.json()),
        fetch(`${API_URL}/score/text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ 
            text: "Switched to Stripe Elements. Considered keeping our custom form but rejected it because it increases our PCI compliance scope. Risk: if Stripe is down, we cannot accept payments, but historically their uptime is >99.99%. Added a circuit breaker that disables the checkout button and shows a clear error state if the Stripe JS fails to load.", 
            domain: "code_review" 
          })
        }).then(r => r.json())
      ]);
      setRes2a(a);
      setRes2b(b);
    } finally {
      setLoading2(false);
    }
  }

  const renderSignal = (res: AnalysisResult | null, targetSignal: string) => {
    if (!res) return null;
    const sig = res.signals.find(s => s.name === targetSignal);
    if (!sig) return <div style={{ color: "#859490", fontSize: "12px", marginTop: "12px" }}>Signal not triggered</div>;
    
    return (
      <div style={{ marginTop: "16px", padding: "12px", background: "rgba(255,255,255,0.05)", borderRadius: "6px", borderLeft: `3px solid ${sig.score > 0.5 ? "#22c55e" : "#ef4444"}` }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
          <strong style={{ color: "#dde4e0" }}>{sig.name.replace(/_/g, " ")}</strong>
          <span style={{ color: sig.score > 0.5 ? "#22c55e" : "#ef4444", fontWeight: "bold" }}>{(sig.score * 100).toFixed(0)}%</span>
        </div>
        <div style={{ fontSize: "12px", color: "#859490", marginBottom: "8px" }}>{sig.reason}</div>
        <div style={{ fontSize: "11px", fontFamily: "var(--mono)", color: "#a78bfa", background: "rgba(0,0,0,0.3)", padding: "8px", borderRadius: "4px", wordBreak: "break-all" }}>
          {sig.detail}
        </div>
      </div>
    );
  };

  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "48px 24px" }}>
      <div style={{ marginBottom: "48px" }}>
        <h1 style={{ fontSize: "36px", marginBottom: "16px", color: "white" }}>The Sharpest Signals</h1>
        <p style={{ fontSize: "18px", color: "#859490", maxWidth: "800px", lineHeight: 1.5 }}>
          The internet doesn't need another generic LLM classifier. SlopGuard introduces <strong>three novel signals</strong> that evaluate the underlying cognitive reasoning structure of text. You cannot prompt-engineer your way past these.
        </p>
      </div>

      {/* SECTION 1 */}
      <section className="panel" style={{ marginBottom: "32px" }}>
        <div style={{ padding: "24px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <h2 style={{ margin: "0 0 8px 0", color: "#a78bfa" }}>1. Epistemic Cowardice</h2>
          <p style={{ margin: 0, color: "#859490" }}>AI heavily hedges its claims ("could potentially", "in some cases"). Human experts make falsifiable commitments ("will drop latency by 40ms"). This signal measures the ratio of hedges to firm commitments.</p>
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", padding: "24px" }}>
          <div>
            <h3 style={{ fontSize: "14px", color: "#ef4444", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>The Hedged AI Draft</h3>
            <div style={{ padding: "16px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "6px", color: "#dde4e0", minHeight: "120px", fontSize: "15px", lineHeight: 1.6 }}>
              We might want to update the database query because it <span style={{ color: "#ef4444", fontWeight: "bold" }}>could potentially</span> improve performance for <span style={{ color: "#ef4444", fontWeight: "bold" }}>some users</span> in <span style={{ color: "#ef4444", fontWeight: "bold" }}>certain scenarios</span>.
            </div>
            {renderSignal(res1a, "epistemic_cowardice")}
          </div>
          <div>
            <h3 style={{ fontSize: "14px", color: "#22c55e", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>The Committed Human</h3>
            <div style={{ padding: "16px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "6px", color: "#dde4e0", minHeight: "120px", fontSize: "15px", lineHeight: 1.6 }}>
              Update the users query to add a composite index on (org_id, created_at). Profiling showed full table scans causing <span style={{ color: "#22c55e", fontWeight: "bold" }}>800ms latency</span> on the dashboard. This <span style={{ color: "#22c55e", fontWeight: "bold" }}>will bring latency under 50ms</span>.
            </div>
            {renderSignal(res1b, "epistemic_cowardice")}
          </div>
        </div>
        <div style={{ padding: "0 24px 24px 24px" }}>
          <button onClick={scoreSection1} disabled={loading1} style={{ width: "100%", padding: "12px", background: "#a78bfa", color: "#0c111c", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>
            {loading1 ? "Analyzing Epistemic State..." : "Analyze Hedge Ratio"}
          </button>
        </div>
      </section>

      {/* SECTION 2 */}
      <section className="panel" style={{ marginBottom: "32px" }}>
        <div style={{ padding: "24px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <h2 style={{ margin: "0 0 8px 0", color: "#a78bfa" }}>2. Counterfactual Absence</h2>
          <p style={{ margin: 0, color: "#859490" }}>AI text lives purely on the "happy path". It describes what is. Human reasoning explicitly describes what was rejected, what could go wrong, and what trade-offs were accepted.</p>
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", padding: "24px" }}>
          <div>
            <h3 style={{ fontSize: "14px", color: "#ef4444", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>Happy Path Slop</h3>
            <div style={{ padding: "16px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "6px", color: "#dde4e0", minHeight: "150px", fontSize: "15px", lineHeight: 1.6 }}>
              Implemented the new payment flow as requested. It works great and all tests pass.
            </div>
            {renderSignal(res2a, "counterfactual_absence")}
          </div>
          <div>
            <h3 style={{ fontSize: "14px", color: "#22c55e", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>Explicit Trade-offs</h3>
            <div style={{ padding: "16px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "6px", color: "#dde4e0", minHeight: "150px", fontSize: "15px", lineHeight: 1.6 }}>
              Switched to Stripe Elements. <span style={{ color: "#22c55e", fontWeight: "bold" }}>Considered keeping our custom form but rejected it because</span> it increases our PCI compliance scope. <span style={{ color: "#22c55e", fontWeight: "bold" }}>Risk: if Stripe is down, we cannot accept payments</span>, but historically their uptime is &gt;99.99%.
            </div>
            {renderSignal(res2b, "counterfactual_absence")}
          </div>
        </div>
        <div style={{ padding: "0 24px 24px 24px" }}>
          <button onClick={scoreSection2} disabled={loading2} style={{ width: "100%", padding: "12px", background: "#a78bfa", color: "#0c111c", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: "pointer" }}>
            {loading2 ? "Scanning for Counterfactuals..." : "Analyze Trade-offs"}
          </button>
        </div>
      </section>

      {/* SECTION 3 */}
      <section className="panel">
        <div style={{ padding: "24px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <h2 style={{ margin: "0 0 8px 0", color: "#a78bfa" }}>3. Vocabulary Novelty Collapse</h2>
          <p style={{ margin: 0, color: "#859490" }}>Humans introduce terminology progressively as they build context. AI scatters technical terms uniformly across the text to simulate expertise, resulting in a flat novelty curve.</p>
        </div>
        
        <div style={{ padding: "24px" }}>
          <div style={{ marginBottom: "24px" }}>
            <h3 style={{ fontSize: "14px", color: "#ef4444", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>The Uniform AI Distribution</h3>
            <p style={{ color: "#859490", fontSize: "14px", fontStyle: "italic" }}>"{text3a}"</p>
            <VocabularyNoveltyCurve text={text3a} />
          </div>
          
          <div style={{ marginTop: "48px" }}>
            <h3 style={{ fontSize: "14px", color: "#22c55e", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "12px" }}>The Progressive Human Distribution</h3>
            <p style={{ color: "#859490", fontSize: "14px", fontStyle: "italic" }}>"{text3b}"</p>
            <VocabularyNoveltyCurve text={text3b} />
          </div>
        </div>
      </section>
      
      <div style={{ textAlign: "center", marginTop: "48px" }}>
        <a href="/dashboard" style={{ display: "inline-block", background: "white", color: "#0c111c", padding: "12px 24px", borderRadius: "8px", textDecoration: "none", fontWeight: "bold" }}>
          Return to Dashboard
        </a>
      </div>
    </div>
  );
}
