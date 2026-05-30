"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const domains = [
  "general",
  "code_review",
  "docs",
  "hiring",
  "communications",
  "content",
  "academia",
  "marketplace",
  "social_news",
];

const demoTexts: Record<string, string> = {
  code_review:
    "Fixed JWT secret exposure in auth/middleware.js — previous implementation logged the full token on line 47, appearing in CloudWatch logs. Considered environment variables but rejected that because our pipeline doesn't support secret rotation. Switched to AWS Secrets Manager with 30-day rotation. This breaks if Secrets Manager API is unavailable — added 5s timeout with cached fallback. Edge case: if cache is empty AND SM is down, auth fails. Accepted that risk.",
  docs:
    "Run `npm run db:migrate` to create the user_sessions table with 4 indexes (email, token, expires_at, user_id). Takes ~12 minutes on a 50 GB PostgreSQL 15 database. If it fails, the transaction rolls back — no partial state. Known issue: created_at on audit_logs is not indexed. Queries filtering by date range will full-scan on tables larger than ~500k rows.",
  hiring:
    "At PayFlow I reduced failed invoice retries by 22% by adding queue backoff and merchant-specific retry windows. Your billing infrastructure role maps directly to that work. I led the migration from Jenkins to GitHub Actions across 8 microservices — cut CI time from 45 min to 12 min. Reduced API latency 40% (200ms → 120ms p95) via Redis caching.",
  communications:
    "Decision: ship the smaller importer on Friday. Owner: Riya. Blocker: CSV date parser — Amit patches by 4 PM, QA retests the 12 failing rows. Fallback: Saturday maintenance window if patch isn't ready.",
  content:
    "We measured onboarding drop-off across 1,240 trial accounts and found the second workspace invite caused 38% of exits. Removing that step reduced median setup time from 11 to 6 minutes. A/B test ran for 30 days with 18,400 sessions.",
  academia:
    "Evaluated on MMLU (Hendrycks et al., 2021) using 5-shot prompting. Our model achieved 78.3% accuracy (95% CI: 77.1–79.5%), vs 76.1% for the baseline. Limitation: benchmark over-represents STEM. Table 3 ablation: removing attention pooling decreased F1 by 3.2 points (87.4→84.2).",
  marketplace:
    "XL black hoodie shrank ~2 cm after first cold wash. Zipper stayed smooth and sleeve cuffs didn't pill after 3 weeks. Runs large — size down if between sizes. Battery lasts ~6 hours with Bluetooth on, not the advertised 10.",
  social_news:
    "Bureau of Labor Statistics May 15 report: unemployment fell to 3.8% from 4.1% in April. Commissioner Shambaugh noted leisure and hospitality added 42,000 jobs, strongest month since January.",
  general:
    "Updated the authentication module to improve security and enhance user experience. This comprehensive change follows best practices and provides a robust solution for all users.",
};

interface SignalResult {
  name: string;
  score: number;
  weight: number;
  label: string;
  reason: string;
}

interface ScoreResponse {
  score: number;
  oversight: string;
  domain: string;
  summary: string;
  reasons: string[];
  signals: SignalResult[];
  highlights: string[];
  relative?: RelativeScore;
}

interface BatchItem {
  score: number;
  oversight: string;
}

interface BatchCluster {
  type: string;
  item_indexes: number[];
  reason: string;
}

interface BatchResult {
  clusters: BatchCluster[];
  items: BatchItem[];
}

interface CitationItem {
  citation: string;
  status: string;
  reason: string;
}

interface CitationResult {
  citations: CitationItem[];
}

interface TimelinePoint {
  week: string;
  score: number;
}

interface Hotspot {
  area: string;
  risk: string;
  count: number;
}

interface RepoResult {
  score: number;
  oversight: string;
  timeline: TimelinePoint[];
  hotspots: Hotspot[];
}

interface PersonalSummary {
  total_scored: number;
  average_score: number;
  low_oversight_percent: number;
  feedback: { total: number };
}

interface SubmissionStatus {
  primary_deliverables: { all_8_track_adapters: string };
  tracks: Record<string, string[]>;
}

interface MetricsResult {
  precision: number;
  recall: number;
  f1: number;
  matrix: { tp: number; fp: number; fn: number; tn: number };
}

interface LeaderboardItem {
  domain?: string;
  repo?: string;
  score: number;
  prev_score?: number;
}

type Tab = "scan" | "pr" | "repo" | "batch" | "citations" | "personal" | "metrics";

// ---- Ticker types ----
interface TickerDomainAvg {
  avg: number;
  delta: number;
  count: number;
}

interface TickerSnapshot {
  window_seconds: number;
  total_scored: number;
  domain_averages: Record<string, TickerDomainAvg>;
  top_signal: string;
  top_signal_rate: number;
  hottest_repo: { name: string; count: number; avg: number } | null;
  global_avg: number;
  global_delta: number;
  slop_rate: number;
  timestamp: number;
}

interface RelativeScore {
  raw: number;
  repo_mean: number | null;
  repo_percentile: number | null;
  author_mean: number | null;
  global_mean: number | null;
  global_percentile: number | null;
  verdict: string;
  context: string;
  baseline_confidence: string;
}

async function postJson(path: string, body: unknown) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path} failed with ${response.status}`);
  return response.json();
}

function Spinner() {
  return <div className="spinner" />;
}

function SkeletonPanel() {
  return (
    <div>
      <div className="skeleton skeleton-line" />
      <div className="skeleton skeleton-line" />
      <div className="skeleton skeleton-line" />
      <div className="skeleton skeleton-block" />
    </div>
  );
}

function TypewriterText({ text, speed = 25, delay = 0 }: { text: string; speed?: number; delay?: number }) {
  const [displayedText, setDisplayedText] = useState("");
  const [complete, setComplete] = useState(false);
  const [started, setStarted] = useState(delay === 0);

  useEffect(() => {
    if (delay > 0) {
      const startTimeout = setTimeout(() => {
        setStarted(true);
      }, delay);
      return () => clearTimeout(startTimeout);
    }
  }, [delay]);

  useEffect(() => {
    if (!started) return;

    let i = 0;
    setDisplayedText("");
    setComplete(false);
    const timer = setInterval(() => {
      if (i < text.length) {
        setDisplayedText(text.substring(0, i + 1));
        i++;
      } else {
        setComplete(true);
        clearInterval(timer);
      }
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed, started]);

  return (
    <>
      {displayedText}
      {started && <span className={`typewriter-cursor ${complete ? "complete" : ""}`}>_</span>}
    </>
  );
}

function scoreColorClass(score: number): string {
  if (score >= 65) return "score-green";
  if (score >= 40) return "score-yellow";
  return "score-red";
}

function signalBarColorClass(score: number): string {
  if (score >= 0.65) return "green";
  if (score >= 0.4) return "yellow";
  return "red";
}

// ─── Custom Domain Selector ──────────────────────────────────────────────────
const DOMAIN_LABELS: Record<string, string> = {
  general:        "General",
  code_review:    "Code Review",
  docs:           "Docs & KBs",
  hiring:         "Hiring",
  communications: "Communications",
  content:        "Content & SEO",
  academia:       "Academia",
  marketplace:    "Marketplace",
  social_news:    "Social & News",
};

function DomainSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="domain-select" ref={ref}>
      <button
        type="button"
        className="domain-select-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{DOMAIN_LABELS[value] ?? value}</span>
        <svg width="10" height="6" viewBox="0 0 10 6" fill="none" aria-hidden="true">
          <path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {open && (
        <ul className="domain-select-menu" role="listbox">
          {domains.map((d) => (
            <li
              key={d}
              role="option"
              aria-selected={d === value}
              className={`domain-select-option${d === value ? " selected" : ""}`}
              onClick={() => { onChange(d); setOpen(false); }}
            >
              {DOMAIN_LABELS[d] ?? d}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
// Calls /signals/vocabulary-novelty and renders an inline SVG sparkline.
// Human pattern: high → declining with spikes. AI pattern: flat line.
function VocabularyCurveChart({ text }: { text: string }) {
  const [curve, setCurve] = useState<number[]>([]);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!text || text.length < 50) return;
    setLoading(true);
    fetch(`${API_URL}/signals/vocabulary-novelty`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, domain: "general" }),
    })
      .then((r) => r.json())
      .then((d) => {
        setCurve(d.curve || []);
        setAnalysis(d.analysis || null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [text]);

  if (loading) return <p className="muted" style={{ marginTop: 12 }}>Computing vocabulary curve…</p>;
  if (!curve.length || !analysis) return null;

  // Don't show the chart if there aren't enough sentences for a meaningful curve
  const sentenceCount = curve.length;
  if (sentenceCount < 6) {
    return (
      <div className="vocab-curve-card">
        <div className="vocab-curve-header">
          <span>⭐ Vocabulary Novelty Curve</span>
          <span className="vocab-verdict" style={{ color: "var(--i3)" }}>needs more text</span>
        </div>
        <p style={{ fontSize: 12, color: "var(--i3)", marginTop: 4 }}>
          Requires 6+ sentences for a meaningful curve. This signal is most useful on full PR descriptions, articles, and longer documents.
        </p>
      </div>
    );
  }

  const W = 340, H = 72, pad = 6;
  const max = Math.max(...curve, 0.01);
  const pts = curve.map((v, i) => {
    const x = pad + (i / Math.max(curve.length - 1, 1)) * (W - pad * 2);
    const y = H - pad - (v / max) * (H - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  // Area fill path
  const firstX = pad;
  const lastX  = pad + (W - pad * 2);
  const areaPath = `M${firstX},${H - pad} L${pts.split(" ").map((p, i) => {
    const [x, y] = p.split(",");
    return `${x},${y}`;
  }).join(" L")} L${lastX},${H - pad} Z`;

  const verdict = String(analysis.verdict || "");
  const verdictColor = verdict === "human_curve" ? "#3fb950"
    : verdict === "mixed_curve" ? "#d29922"
    : "#f85149";
  const gradId = `vcGrad_${verdict}`;

  return (
    <div className="vocab-curve-card">
      <div className="vocab-curve-header">
        <span>⭐ Vocabulary Novelty Curve</span>
        <span className="vocab-verdict" style={{ color: verdictColor }}>{verdict.replace(/_/g, " ")}</span>
      </div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: "block", margin: "6px 0" }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={verdictColor} stopOpacity=".25" />
            <stop offset="100%" stopColor={verdictColor} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill={`url(#${gradId})`} />
        <polyline points={pts} fill="none" stroke={verdictColor} strokeWidth="1.8" strokeLinejoin="round" />
        {curve.map((v, i) => {
          const x = pad + (i / Math.max(curve.length - 1, 1)) * (W - pad * 2);
          const y = H - pad - (v / max) * (H - pad * 2);
          return <circle key={i} cx={x} cy={y} r="2.5" fill={verdictColor} opacity=".8" />;
        })}
      </svg>
      <div className="vocab-curve-stats">
        <span>variance={Number(analysis.variance).toFixed(3)}</span>
        <span>slope={Number(analysis.slope).toFixed(3)}</span>
        <span>spikes={String(analysis.spike_count)}</span>
        <span>n={String(curve.length)} sentences</span>
      </div>
      <small className="muted" style={{ display:"block", marginTop:6, fontSize:11, color:"var(--ink-3)" }}>
        Human: high early → declining with spikes · AI: flat uniform line
      </small>
    </div>
  );
}

function TrendArrow({ current, previous }: { current: number; previous?: number }) {
  if (previous === undefined || previous === null) return null;
  const diff = current - previous;
  if (Math.abs(diff) < 1) return null;
  if (diff > 0) return <span className="trend-up">▲</span>;
  return <span className="trend-down">▼</span>;
}

function OversightPill({ value }: { value: string }) {
  return <span className={`pill ${value}`}>{value}</span>;
}

function TickerBar() {
  const [snapshot, setSnapshot] = useState<TickerSnapshot | null>(null);
  const [live, setLive] = useState(false);
  const [animating, setAnimating] = useState(false);
  const prevRef = useRef<TickerSnapshot | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/ticker`)
      .then((res) => res.json())
      .then((data) => {
        setSnapshot(data);
        prevRef.current = data;
      })
      .catch(() => {});

    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      eventSource = new EventSource(`${API_URL}/ticker/live`);
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as TickerSnapshot;
          prevRef.current = snapshot;
          setAnimating(true);
          setSnapshot(data);
          setLive(true);
          setTimeout(() => setAnimating(false), 600);
        } catch {}
      };
      eventSource.onerror = () => {
        setLive(false);
        eventSource?.close();
        reconnectTimer = setTimeout(connect, 5000);
      };
    }

    connect();
    return () => {
      eventSource?.close();
      clearTimeout(reconnectTimer);
    };
  }, []);

  if (!snapshot) return null;

  const topDomains = Object.entries(snapshot.domain_averages || {}).slice(0, 4);

  return (
    <div className={`ticker ${live ? "ticker-live" : ""} ${animating ? "ticker-flash" : ""}`}>
      <div className="ticker-header">
        <span className={`ticker-dot ${live ? "ticker-dot-on" : "ticker-dot-off"}`} />
        <strong>LIVE</strong>
        <span className="ticker-period">60s window</span>
      </div>
      <div className="ticker-divider" />
      <div className="ticker-stats">
        <div className="ticker-stat">
          <span className="ticker-stat-value">{snapshot.total_scored}</span>
          <span className="ticker-stat-label">scored</span>
        </div>
        <div className="ticker-stat">
          <span className="ticker-stat-value">{snapshot.global_avg.toFixed(1)}</span>
          <span className="ticker-stat-label">
            global
            {snapshot.global_delta !== 0 && (
              <span className={snapshot.global_delta > 0 ? "trend-up" : "trend-down"}>
                {" "}{snapshot.global_delta > 0 ? "↑" : "↓"}{Math.abs(snapshot.global_delta).toFixed(1)}
              </span>
            )}
          </span>
        </div>
        {topDomains.map(([domain, da]) => (
          <div className="ticker-stat" key={domain}>
            <span className="ticker-stat-value">{da.avg.toFixed(1)}</span>
            <span className="ticker-stat-label">
              {domain.replace("_", " ")}
              {da.delta !== 0 && (
                <span className={da.delta > 0 ? "trend-up" : "trend-down"}>
                  {" "}{da.delta > 0 ? "↑" : "↓"}{Math.abs(da.delta).toFixed(1)}
                </span>
              )}
            </span>
          </div>
        ))}
        {snapshot.hottest_repo && (
          <div className="ticker-stat ticker-hot">
            <span className="ticker-stat-value">{snapshot.hottest_repo.avg.toFixed(1)}</span>
            <span className="ticker-stat-label">
              {snapshot.hottest_repo.name} ({snapshot.hottest_repo.count})
            </span>
          </div>
        )}
      </div>
      <div className="ticker-signal">
        <span className="ticker-signal-label">Top signal:</span>
        <span className="ticker-signal-value">{snapshot.top_signal.replace(/_/g, " ")}</span>
        <span className="ticker-signal-pct">{(snapshot.top_signal_rate * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}

const NOVEL_SIGNALS: Record<string, { label: string; badge: string; why: string }> = {
  epistemic_cowardice: {
    label: "Epistemic Cowardice",
    badge: "⭐ Novel",
    why: "Detects systematic avoidance of taking positions — hedge clustering, false balance, opinion laundering.",
  },
  counterfactual_absence: {
    label: "Counterfactual Absence",
    badge: "⭐ Novel",
    why: "Detects missing alternatives, failure modes, and tradeoffs. AI generates the happy path; humans think about what breaks.",
  },
  vocabulary_novelty: {
    label: "Vocabulary Novelty",
    badge: "⭐ Novel",
    why: "Analyzes the SHAPE of vocabulary introduction over time. Human: decreasing curve with spikes. AI: flat uniform distribution.",
  },
};

// Human-readable names for standard signals
const SIGNAL_LABELS: Record<string, string> = {
  human_delta_score:        "editing artifacts",
  semantic_uniqueness_proxy: "semantic uniqueness",
  information_density:      "information density",
  why_vs_what:              "causal reasoning",
  template_structure:       "template structure",
  specificity:              "specificity",
  evidence_density:         "evidence density",
};

function renderSignalReason(reason: string) {
  if (!reason) return null;

  // Check if it's a key=value metrics string
  if (reason.includes("=")) {
    const parts = reason.split(/\s+/).filter(Boolean);
    const kvPairs: Array<{ key: string; val: string }> = [];

    for (const part of parts) {
      const eqIdx = part.indexOf("=");
      if (eqIdx > 0) {
        kvPairs.push({
          key: part.substring(0, eqIdx).replace(/_/g, " "),
          val: part.substring(eqIdx + 1)
        });
      } else {
        kvPairs.push({ key: "", val: part });
      }
    }

    if (kvPairs.length > 0) {
      return (
        <div className="signal-telemetry-grid">
          {kvPairs.map((pair, idx) => (
            <div key={idx} className="telemetry-pill">
              {pair.key ? (
                <>
                  <span className="telemetry-key">{pair.key}</span>
                  <span className="telemetry-val">{pair.val}</span>
                </>
              ) : (
                <span className="telemetry-raw">{pair.val}</span>
              )}
            </div>
          ))}
        </div>
      );
    }
  }

  return <small className="signal-reason">{reason}</small>;
}

function SignalBarChart({ signals }: { signals: SignalResult[] }) {
  const novel = signals.filter((s) => s.name in NOVEL_SIGNALS);
  const standard = signals.filter((s) => !(s.name in NOVEL_SIGNALS));

  const renderSignal = (signal: SignalResult, isNovel = false) => {
    const meta = isNovel ? NOVEL_SIGNALS[signal.name] : null;
    const pct = Math.round(signal.score * 100);
    const colorClass = signal.score >= 0.65 ? "green" : signal.score >= 0.4 ? "yellow" : "red";

    // Hide low-weight signals that scored neutral and add no information
    if (!isNovel && signal.weight <= 0.3 && signal.score < 0.1) return null;

    return (
      <div key={signal.name} className={`signal${isNovel ? " signal-novel" : ""} signal-${colorClass}`}>
        <div className="signal-row">
          <span className="signal-name">
            {meta ? meta.label : (SIGNAL_LABELS[signal.name] ?? signal.name.replace(/_/g, " "))}
          </span>
          {isNovel && <span className="novel-badge">Novel</span>}
          <span className="signal-pct">{pct}%</span>
        </div>
        <div className="signal-bar-track">
          <div className={`signal-bar-fill ${colorClass}`} style={{ width: `${pct}%` }} />
        </div>
        {isNovel && meta && <small className="novel-why">{meta.why}</small>}
        {renderSignalReason(signal.reason)}
      </div>
    );
  };

  return (
    <div className="signals">
      {novel.length > 0 && (
        <div className="novel-signals-section">
          <div className="novel-signals-header">⭐ Novel Signals</div>
          <div className="standard-signals-section">
            {novel.map((s) => renderSignal(s, true))}
          </div>
        </div>
      )}
      <div className="standard-signals-section">
        {standard.map((s) => renderSignal(s, false))}
      </div>
    </div>
  );
}

function RelativeScoreCard({ relative }: { relative: RelativeScore | null }) {
  if (!relative) return null;
  const confidence = relative.baseline_confidence || "none";
  const confidenceLabel = { high: "High", medium: "Medium", low: "Low", none: "None" }[confidence] || "None";
  return (
    <div className="relative-card">
      <div className="relative-header">
        <strong>Contextual Score</strong>
        <span className={`confidence confidence-${confidence}`}>{confidenceLabel} confidence</span>
      </div>
      <p className="relative-context">{relative.context}</p>
      <div className="relative-bars">
        {relative.repo_mean !== null && (
          <div className="relative-bar-row">
            <span className="relative-bar-label">Repo avg</span>
            <div className="relative-bar-track">
              <div className="relative-bar-fill" style={{ width: `${relative.repo_mean}%` }}>
                <span>{relative.repo_mean}</span>
              </div>
            </div>
          </div>
        )}
        {relative.author_mean !== null && (
          <div className="relative-bar-row">
            <span className="relative-bar-label">Your avg</span>
            <div className="relative-bar-track">
              <div className="relative-bar-fill" style={{ width: `${relative.author_mean}%` }}>
                <span>{relative.author_mean}</span>
              </div>
            </div>
          </div>
        )}
        {relative.global_mean !== null && (
          <div className="relative-bar-row">
            <span className="relative-bar-label">Global avg</span>
            <div className="relative-bar-track">
              <div className="relative-bar-fill relative-bar-global" style={{ width: `${relative.global_mean}%` }}>
                <span>{relative.global_mean}</span>
              </div>
            </div>
          </div>
        )}
        <div className="relative-bar-row">
          <span className="relative-bar-label">This score</span>
          <div className="relative-bar-track">
            <div className={`relative-bar-fill relative-bar-this ${relative.raw >= (relative.repo_mean || 50) ? "bar-green" : "bar-red"}`}
              style={{ width: `${relative.raw}%` }}>
              <span>{relative.raw}</span>
            </div>
          </div>
        </div>
      </div>
      {relative.repo_percentile !== null && (
        <p className="relative-percentile">
          In the <strong>{relative.repo_percentile}th</strong> percentile for this repo
        </p>
      )}
    </div>
  );
}

function SignalList({ result }: { result: ScoreResponse | null }) {
  if (!result) return <p className="muted">Run a score to see oversight signals.</p>;
  return (
    <>
      <div className={`verdict-card verdict-${result.oversight}`}>
        <div className="verdict-card-glow" />
        <div className="verdict-icon">
          {result.oversight === "high" && (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M13.333 4L5.999 11.333 2.666 8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          {result.oversight === "mixed" && (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          {result.oversight === "low" && (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
          {result.oversight === "insufficient" && (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M8 12V8M8 4h.01" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </div>
        <div className="verdict-content">
          <span className="verdict-label">Oversight Verdict</span>
          <h3 className="verdict-title">{result.summary}</h3>
        </div>
      </div>
      {result.relative && <RelativeScoreCard relative={result.relative} />}
      <SignalBarChart signals={result.signals} />
      {result.highlights?.length > 0 && (
        <div className="callout">
          <strong>Weak passages</strong>
          {result.highlights.map((item: string) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      )}
    </>
  );
}

export default function Home() {
  const [tab, setTab] = useState<Tab>("scan");
  const [text, setText] = useState(demoTexts.content);
  const [domain, setDomain] = useState("content");
  const [result, setResult] = useState<ScoreResponse | null>(null);
  const [prTitle, setPrTitle] = useState("Improve billing retry behavior");
  const [prDescription, setPrDescription] = useState("Updated billing files and improved retry handling. This fixes issues and enhances reliability.");
  const [prDiff, setPrDiff] = useState("+ retryCount = Math.min(retryCount + 1, 3)\n+ idempotencyWindowMinutes = 10\n+ because duplicate Stripe webhooks were replayed during deploys");
  const [prResult, setPrResult] = useState<ScoreResponse | null>(null);
  const [repoName, setRepoName] = useState("facebook/react");
  const [repoResult, setRepoResult] = useState<RepoResult | null>(null);
  const [batchText, setBatchText] = useState(
    [
      "Amazing product. Great quality and highly recommend. It works perfectly.",
      "Amazing product. Great quality and highly recommend. It works perfectly.",
      "The 5000 mAh battery lasted 9 hours and the USB-C port got warm after the third charge.",
      "I am excited to apply for this role at your company. My skills make me a great fit.",
    ].join("\n---\n"),
  );
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);
  const [citations, setCitations] = useState("doi:10.1038/s41586-020-2649-2\nSmith, A. The Future of AI Content, 2025");
  const [citationResult, setCitationResult] = useState<CitationResult | null>(null);
  const [metrics, setMetrics] = useState<MetricsResult | null>(null);
  const [personal, setPersonal] = useState<PersonalSummary | null>(null);
  const [status, setStatus] = useState<SubmissionStatus | null>(null);
  const [sites, setSites] = useState<LeaderboardItem[]>([]);
  const [repos, setRepos] = useState<LeaderboardItem[]>([]);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  const activeScore = useMemo(() => result || prResult || repoResult, [result, prResult, repoResult]);

  const targetScore = activeScore ? Math.round(activeScore.score) : null;
  const [animatedScore, setAnimatedScore] = useState<number | null>(null);
  const prevTargetRef = useRef<number | null>(null);

  useEffect(() => {
    if (targetScore === null) {
      setAnimatedScore(null);
      prevTargetRef.current = null;
      return;
    }

    if (prevTargetRef.current === null) {
      setAnimatedScore(targetScore);
      prevTargetRef.current = targetScore;
      return;
    }

    if (prevTargetRef.current === targetScore) {
      return;
    }

    const startScore = animatedScore ?? 0;
    prevTargetRef.current = targetScore;

    let start = performance.now();
    const duration = 800; // 0.8 seconds
    const delta = targetScore - startScore;

    let active = true;

    function step() {
      if (!active) return;
      const now = performance.now();
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3); // Ease out cubic
      setAnimatedScore(Math.round(startScore + delta * ease));

      if (progress < 1) {
        requestAnimationFrame(step);
      }
    }

    requestAnimationFrame(step);
    return () => {
      active = false;
    };
  }, [targetScore]);

  useEffect(() => {
    fetch(`${API_URL}/leaderboard/sites`).then((res) => res.json()).then((data) => setSites(data.items)).catch(() => {});
    fetch(`${API_URL}/leaderboard/repos`).then((res) => res.json()).then((data) => setRepos(data.items)).catch(() => {});
  }, []);

  async function scoreText() {
    setLoading("scan");
    setResult(null);
    setError("");
    try {
      const scored = await postJson("/score/text", { text, domain });
      setResult(scored);
      await postJson("/events/score", { url: "dashboard://scan", title: "Dashboard Scan", domain, score: scored.score, oversight: scored.oversight });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to score text.");
    } finally {
      setLoading("");
    }
  }

  async function scorePr() {
    setLoading("pr");
    setPrResult(null);
    setError("");
    try {
      const scored = await postJson("/score/pr", { title: prTitle, description: prDescription, diff: prDiff, comments: ["Why cap retries at 3?", "LGTM"] });
      setPrResult(scored);
      await postJson("/events/score", { url: "dashboard://pr", title: prTitle, domain: "code_review", score: scored.score, oversight: scored.oversight });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to score PR.");
    } finally {
      setLoading("");
    }
  }

  async function scoreRepo() {
    setLoading("repo");
    setRepoResult(null);
    setError("");
    try {
      // Try to fetch real PRs from GitHub API first
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      let pullRequests: Array<{title: string; description: string; diff: string; comments: string[]}> = [];

      try {
        const prRes = await fetch(`https://api.github.com/repos/${repoName}/pulls?state=closed&per_page=8&sort=updated`);
        if (prRes.ok) {
          const prs = await prRes.json();
          pullRequests = prs
            .filter((pr: {title: string; body: string | null}) => pr.title && pr.body && pr.body.length > 20)
            .slice(0, 6)
            .map((pr: {title: string; body: string | null; number: number}) => ({
              title: pr.title,
              description: (pr.body || "").slice(0, 800),
              diff: `PR #${pr.number}`,
              comments: [],
            }));
        }
      } catch {
        // GitHub API unavailable — fall through to synthetic
      }

      // Fallback: use varied synthetic PRs that produce different scores
      if (pullRequests.length === 0) {
        pullRequests = [
          {
            title: "Fix JWT secret exposure in auth middleware",
            description: `Fixed JWT secret logged on line 47 of auth/middleware.js — appeared in CloudWatch logs. Considered env vars but rejected because pipeline lacks rotation support. Switched to AWS Secrets Manager with 30-day rotation. This breaks if SM API is unavailable — added 5s timeout with cached fallback. Accepted that risk.`,
            diff: "- logToken(jwt)\n+ // token logging removed",
            comments: ["Good catch", "Why not env vars?", "LGTM after discussion"],
          },
          {
            title: "Update docs",
            description: "Updated docs and improved content. This makes the docs better and enhances user experience.",
            diff: "+ # Setup\n+ This guide explains setup.",
            comments: ["LGTM"],
          },
          {
            title: "Add Redis caching for user profiles",
            description: `Added Redis caching for /api/user-profile. Considered Memcached but rejected — need pub/sub for cache invalidation on profile updates. TTL 300s: shorter hammers DB on miss storms, longer risks stale data after password changes. Known gap: no invalidation on admin edits. Added manual flush endpoint for support team.`,
            diff: "+ cache.set(key, profile, ttl=300)",
            comments: ["What's the TTL rationale?", "Approved"],
          },
          {
            title: "Refactor authentication module",
            description: "Refactored the authentication module to improve code quality and maintainability. Various improvements were made to ensure better performance going forward.",
            diff: "+ // refactored",
            comments: ["LGTM"],
          },
          {
            title: "Add rate limiting to search API",
            description: `Rate-limited /api/v2/search after Grafana showed 3 customers sending 400+ rps, spiking p99 from 120ms to 2.8s. Limit: 60 rps/key, 429 + Retry-After. Chose sliding window over token bucket — token bucket allows burst at window boundary. Cluster-wide limit needs Redis counter (+2ms/req); accepted per-instance for now.`,
            diff: "+ @rate_limit(60)",
            comments: ["Why 60 rps?", "Makes sense given the data"],
          },
          {
            title: "Update dependencies",
            description: "Updated various dependencies to their latest versions. This ensures we have the latest security patches and improvements.",
            diff: "+ fastapi==0.115.0",
            comments: ["LGTM"],
          },
        ];
      }

      setRepoResult(
        await postJson("/score/repo", {
          repo: repoName,
          pull_requests: pullRequests,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to score repo.");
    } finally {
      setLoading("");
    }
  }

  async function scoreBatch() {
    setLoading("batch");
    setError("");
    const items = batchText
      .split(/\n---\n/g)
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => ({ text: item, domain: item.toLowerCase().includes("product") || item.toLowerCase().includes("battery") ? "marketplace" : "hiring" }));
    try {
      setBatchResult(await postJson("/score/batch", { items }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to score batch.");
    } finally {
      setLoading("");
    }
  }

  async function verifyCitations() {
    setLoading("citations");
    setError("");
    try {
      setCitationResult(await postJson("/score/citations", { citations: citations.split("\n").map((item) => item.trim()).filter(Boolean) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to verify citations.");
    } finally {
      setLoading("");
    }
  }

  async function loadMetrics() {
    setLoading("metrics");
    setError("");
    try {
      const response = await fetch(`${API_URL}/evaluation/sample`);
      if (!response.ok) throw new Error(`metrics failed with ${response.status}`);
      setMetrics(await response.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load metrics.");
    } finally {
      setLoading("");
    }
  }

  async function loadPersonal() {
    setLoading("personal");
    setError("");
    try {
      const [summaryResponse, statusResponse] = await Promise.all([
        fetch(`${API_URL}/personal/summary`),
        fetch(`${API_URL}/submission/status`),
      ]);
      if (!summaryResponse.ok) throw new Error(`personal failed with ${summaryResponse.status}`);
      if (!statusResponse.ok) throw new Error(`status failed with ${statusResponse.status}`);
      setPersonal(await summaryResponse.json());
      setStatus(await statusResponse.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load personal summary.");
    } finally {
      setLoading("");
    }
  }

  async function sendFeedback(userLabel: "slop" | "reviewed" | "unsure") {
    const active = result || prResult;
    if (!active) return;
    await postJson("/feedback", { text: tab === "pr" ? prDescription : text, domain: tab === "pr" ? "code_review" : domain, user_label: userLabel, score: active.score, url: `dashboard://${tab}` });
    await loadPersonal();
  }

  return (
    <>
    <nav className="site-nav">
      <a className="site-nav-brand" href="#">
        <span className="site-nav-brand-dot" />
        SlopGuard
      </a>
      <div className="site-nav-links">
        <span className="site-nav-link">Docs</span>
        <span className="site-nav-link">API</span>
        <a className="site-nav-link" href="http://localhost:8000/live" target="_blank" rel="noreferrer">Live Feed</a>
        <span className="site-nav-badge">Hackathon 2026</span>
      </div>
    </nav>
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">
            <span className="eyebrow-dot" />
            Slop Scan Hackathon 2026 · Track A — Code Review
          </p>
          <h1><TypewriterText text="SlopGuard" speed={80} /></h1>
          <p className="lede">
            <TypewriterText text="Scores content for human oversight quality — not AI authorship. 10 signals including 3 novel detectors nobody else built." speed={20} delay={1000} />
          </p>
          <div className="hero-badges">
            <span className="hero-badge teal">F1 = 0.926 on 453 samples</span>
            <span className="hero-badge blue">10 Universal Signals</span>
          </div>
        </div>
        <div className="scoreBox">
          <svg className="scoreBox-svg" viewBox="0 0 100 100" aria-hidden="true">
            <defs>
              <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%"   stopColor="#2dd4bf" />
                <stop offset="100%" stopColor="#58a6ff" />
              </linearGradient>
              <linearGradient id="ringGreen" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%"   stopColor="#16a34a" />
                <stop offset="100%" stopColor="#4ade80" />
              </linearGradient>
              <linearGradient id="ringYellow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%"   stopColor="#b45309" />
                <stop offset="100%" stopColor="#fbbf24" />
              </linearGradient>
              <linearGradient id="ringRed" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%"   stopColor="#b91c1c" />
                <stop offset="100%" stopColor="#f87171" />
              </linearGradient>
            </defs>
            {/* Slowly rotating dotted outer guide track */}
            <circle className="ring-track-dots" cx="50" cy="50" r="48" />
            <circle className="ring-track" cx="50" cy="50" r="45" />

            {/* High-tech scanning arc when waiting or loading */}
            <circle
              className={`ring-scan ${loading ? "ring-scan-fast" : ""} ${activeScore ? "ring-scan-hidden" : ""}`}
              cx="50"
              cy="50"
              r="45"
            />

            {/* Central micro pulsing target dot when waiting */}
            {!activeScore && (
              <circle
                className={`ring-center-dot ${loading ? "ring-center-dot-active" : ""}`}
                cx="50"
                cy="50"
                r="3"
              />
            )}

            <circle
              className={`ring-fill ${
                animatedScore !== null
                  ? animatedScore >= 65 ? "ring-fill-green"
                  : animatedScore >= 40 ? "ring-fill-yellow"
                  : "ring-fill-red"
                  : ""
              }`}
              cx="50" cy="50" r="45"
              style={{
                strokeDashoffset: animatedScore !== null
                  ? 283 - (283 * Math.min(animatedScore, 100)) / 100
                  : 283,
              }}
            />
          </svg>
          <div className="scoreBox-inner">
            <span className="scoreBox-label">Score</span>
            <span className={`scoreBox-number ${animatedScore !== null ? scoreColorClass(animatedScore) : ""}`}>
              {animatedScore !== null ? animatedScore : "--"}
            </span>
            <span className={`scoreBox-verdict ${!activeScore ? "waiting" : ""}`}>
              {activeScore?.oversight ?? (loading ? "scoring" : "waiting")}
            </span>
          </div>
        </div>
      </section>

      <TickerBar />
      <nav className="tabs">
        {([
          ["scan",      "Scan"],
          ["pr",        "PR Review"],
          ["repo",      "Repo"],
          ["batch",     "Batch"],
          ["citations", "Citations"],
          ["personal",  "Personal"],
          ["metrics",   "Metrics"],
        ] as [Tab, string][]).map(([id, label]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </nav>

      {error && <div className="errorBox">{error}. Check that the API is running at {API_URL}.</div>}

      {tab === "scan" && (
        <section className="workspace">
          <div className="panel">
            <div className="toolbar">
              <DomainSelect
                value={domain}
                onChange={(d) => {
                  setDomain(d);
                  setText(demoTexts[d] || demoTexts.general);
                }}
              />
              <button onClick={scoreText} disabled={loading === "scan"}>
                {loading === "scan" ? <span className="spinner-inline"><Spinner /> Scoring…</span> : "Score Text"}
              </button>
            </div>
            <textarea value={text} onChange={(event) => setText(event.target.value)} />
            <div className="workspace-tracks-header">
              <span className="tracks-header-dot" />
              <span>Active Channel Adapters</span>
            </div>
            <div className="workspace-tracks">
              {domains.slice(1).map((item) => (
                <div
                  key={item}
                  className={`workspace-track-card${domain === item ? " active" : ""}`}
                  onClick={() => {
                    setDomain(item);
                    setText(demoTexts[item] || demoTexts.general);
                  }}
                >
                  <div className="track-card-status">
                    <span className={`status-dot ${domain === item ? "pulsing" : ""}`} />
                    <span>Adapter Ready</span>
                  </div>
                  <strong className="track-card-title">{item.replace(/_/g, " ")}</strong>
                </div>
              ))}
            </div>
          </div>
          <div className="panel">
            <h2>Signal Breakdown</h2>
            {loading === "scan" ? <SkeletonPanel /> : <SignalList result={result} />}
            {result && <VocabularyCurveChart text={text} />}
            {!result && !loading && (
              <div className="empty-state">
                <div className="empty-state-icon">🔍</div>
                <p className="empty-state-title">No score yet</p>
                <p className="empty-state-desc">Select a domain, paste your content, and hit Score Text to see the signal breakdown.</p>
              </div>
            )}
          </div>
        </section>
      )}

      {tab === "pr" && (
        <section className="workspace">
          <div className="panel formGrid">
            <label>PR Title<input value={prTitle} onChange={(event) => setPrTitle(event.target.value)} /></label>
            <label>Description<textarea value={prDescription} onChange={(event) => setPrDescription(event.target.value)} /></label>
            <label>Diff<textarea value={prDiff} onChange={(event) => setPrDiff(event.target.value)} /></label>
            <button onClick={scorePr} disabled={loading === "pr"}>
              {loading === "pr" ? <span className="spinner-inline"><Spinner /> Scoring…</span> : "Score PR"}
            </button>
          </div>
          <div className="panel">
            <h2>PR Oversight</h2>
            {loading === "pr" ? <SkeletonPanel /> : <SignalList result={prResult} />}
          </div>
        </section>
      )}

      {tab === "batch" && (
        <section className="workspace">
          <div className="panel">
            <p className="muted" style={{marginBottom:12}}>Separate cover letters or reviews with a line containing three dashes.</p>
            <textarea value={batchText} onChange={(event) => setBatchText(event.target.value)} />
            <button onClick={scoreBatch} disabled={loading === "batch"} style={{marginTop:12}}>
              {loading === "batch" ? <span className="spinner-inline"><Spinner /> Clustering…</span> : "Score Batch"}
            </button>
          </div>
          <div className="panel">
            <h2>Batch Clusters</h2>
            {loading === "batch" && <SkeletonPanel />}
            {!loading && !batchResult && <p className="muted">Run batch scoring to find repeated structures.</p>}
            {batchResult?.clusters?.map((cluster, index: number) => (
              <div className="cluster" key={`${cluster.type}-${index}`}>
                <strong>{cluster.type}</strong>
                <span>Items: {cluster.item_indexes.join(", ")}</span>
                <p>{cluster.reason}</p>
              </div>
            ))}
            {batchResult?.items?.map((item, index: number) => (
              <div className="row" key={index}>
                <span>Item {index + 1}</span>
                <OversightPill value={item.oversight} />
                <strong className={scoreColorClass(Math.round(item.score))}>{Math.round(item.score)}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      {tab === "repo" && (
        <section className="workspace">
          <div className="panel formGrid">
            <label>Repository<input value={repoName} onChange={(event) => setRepoName(event.target.value)} placeholder="owner/repo e.g. facebook/react" /></label>
            <p className="muted" style={{fontSize:12}}>Fetches real closed PRs from GitHub if public. Falls back to synthetic PRs showing the score range across different writing quality levels.</p>
            <button onClick={scoreRepo} disabled={loading === "repo"}>
              {loading === "repo" ? <span className="spinner-inline"><Spinner /> Scoring…</span> : "Score Repo"}
            </button>
            {repoResult && (
              <div className="metricGrid">
                <div><span>Repo Score</span><strong>{repoResult.score}</strong></div>
                <div><span>Oversight</span><strong>{repoResult.oversight}</strong></div>
              </div>
            )}
          </div>
          <div className="panel">
            <h2>Slop Velocity</h2>
            {loading === "repo" && <SkeletonPanel />}
            {!loading && !repoResult && <p className="muted">Run repo scoring to see timeline and hotspots.</p>}
            {repoResult && (
              <>
                <div className="timeline">
                  {repoResult.timeline.map((point) => (
                    <div key={point.week}>
                      <span>{point.week}</span>
                      <meter min={0} max={100} value={point.score} />
                      <strong className={scoreColorClass(point.score)}>{point.score}</strong>
                    </div>
                  ))}
                </div>
                <h3>Hotspots</h3>
                {repoResult.hotspots.map((hotspot) => (
                  <div className="cluster" key={`${hotspot.area}-${hotspot.risk}`}>
                    <strong>{hotspot.area}</strong>
                    <p>{hotspot.risk}: {hotspot.count} findings</p>
                  </div>
                ))}
              </>
            )}
          </div>
        </section>
      )}

      {tab === "citations" && (
        <section className="workspace">
          <div className="panel">
            <textarea value={citations} onChange={(event) => setCitations(event.target.value)} />
            <button onClick={verifyCitations} disabled={loading === "citations"}>
              {loading === "citations" ? <span className="spinner-inline"><Spinner /> Checking…</span> : "Verify Citations"}
            </button>
          </div>
          <div className="panel">
            <h2>Citation Status</h2>
            {loading === "citations" && <SkeletonPanel />}
            {!loading && !citationResult && <p className="muted">Run verification to flag citations that need review.</p>}
            {citationResult?.citations?.map((item) => (
              <div className="cluster" key={item.citation}>
                <strong>{item.status}</strong>
                <p>{item.citation}</p>
                <small>{item.reason}</small>
              </div>
            ))}
          </div>
        </section>
      )}

      {tab === "personal" && (
        <section className="workspace">
          <div className="panel">
            <h2>Personal Intelligence</h2>
            <button onClick={loadPersonal} disabled={loading === "personal"}>
              {loading === "personal" ? <span className="spinner-inline"><Spinner /> Loading…</span> : "Refresh Summary"}
            </button>
            {loading === "personal" && <SkeletonPanel />}
            {personal && (
              <div className="metricGrid">
                <div><span>Scored</span><strong>{personal.total_scored}</strong></div>
                <div><span>Avg Score</span><strong>{personal.average_score}</strong></div>
                <div><span>Low Oversight</span><strong>{personal.low_oversight_percent}%</strong></div>
                <div><span>Feedback</span><strong>{personal.feedback.total}</strong></div>
              </div>
            )}
            <div className="feedbackBar">
              <button className="btn-danger"  onClick={() => sendFeedback("slop")}>Mark Slop</button>
              <button className="btn-success" onClick={() => sendFeedback("reviewed")}>Mark Reviewed</button>
              <button className="btn-ghost"   onClick={() => sendFeedback("unsure")}>Unsure</button>
            </div>
          </div>
          <div className="panel">
            <h2>Submission Status</h2>
            {loading === "personal" && <SkeletonPanel />}
            {!loading && !status && <p className="muted">Refresh summary to load the PRD completion map.</p>}
            {status && (
              <>
                <p className="badge high">{status.primary_deliverables.all_8_track_adapters}</p>
                {Object.entries(status.tracks).map(([track, signals]) => (
                  <div className="cluster" key={track}>
                    <strong>{track.replaceAll("_", " ")}</strong>
                    <p>{(signals as string[]).join(", ")}</p>
                  </div>
                ))}
              </>
            )}
          </div>
        </section>
      )}

      {tab === "metrics" && (
        <section className="workspace">
          <div className="panel">
            <h2>Bake-Off Metrics</h2>
            <button onClick={loadMetrics} disabled={loading === "metrics"}>
              {loading === "metrics" ? <span className="spinner-inline"><Spinner /> Loading…</span> : "Run Sample Evaluation"}
            </button>
            {loading === "metrics" && <SkeletonPanel />}
            {metrics && (
              <div className="metricGrid">
                <div className="metric-blue"><span>Precision</span><strong>{metrics.precision}</strong></div>
                <div className="metric-teal"><span>Recall</span><strong>{metrics.recall}</strong></div>
                <div className="metric-green"><span>F1</span><strong>{metrics.f1}</strong></div>
                <div className="metric-gold"><span>TP / FP / FN / TN</span><strong>{metrics.matrix.tp}/{metrics.matrix.fp}/{metrics.matrix.fn}/{metrics.matrix.tn}</strong></div>
              </div>
            )}
          </div>
          <div className="panel">
            <h2>Leaderboards</h2>
            <div className="leaderboards">
              <div>
                <h3>Sites</h3>
                {sites.map((site) => (
                  <div className="row" key={site.domain}>
                    <span>{site.domain}</span>
                    <TrendArrow current={site.score} previous={site.prev_score} />
                    <strong className={scoreColorClass(Math.round(site.score))}>{site.score}</strong>
                  </div>
                ))}
              </div>
              <div>
                <h3>Repos</h3>
                {repos.map((repo) => (
                  <div className="row" key={repo.repo}>
                    <span>{repo.repo}</span>
                    <TrendArrow current={repo.score} previous={repo.prev_score} />
                    <strong className={scoreColorClass(Math.round(repo.score))}>{repo.score}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      <section className="tracks">
        {domains.slice(1).map((item) => (
          <div key={item}>
            <strong>{item.replace(/_/g, " ")}</strong>
            <span>adapter ready</span>
          </div>
        ))}
      </section>
    </main>
    </>
  );
}
