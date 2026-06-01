"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

type AnalysisData = {
  variance: number;
  slope: number;
  spike_count: number;
  entropy: number;
  front_loading: boolean;
  human_score: number;
  verdict: "ai_curve" | "flat_curve" | "mixed_curve" | "human_curve";
};

type APIResponse = {
  curve: number[];
  labels: number[];
  analysis: AnalysisData;
};

export default function VocabularyNoveltyCurve({ text }: { text: string }) {
  const [data, setData] = useState<{ label: number; value: number }[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchCurve() {
      setLoading(true);
      try {
        const res = await fetch(process.env.NEXT_PUBLIC_API_URL + "/signals/vocabulary-novelty", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, domain: "general" }),
        });
        if (res.ok) {
          const json: APIResponse = await res.json();
          const chartData = json.curve.map((val, idx) => ({
            label: idx + 1,
            value: Math.round(val * 100) / 100,
          }));
          setData(chartData);
          setAnalysis(json.analysis);
        }
      } catch (err) {
        console.error("Failed to fetch vocabulary curve", err);
      } finally {
        setLoading(false);
      }
    }
    if (text) fetchCurve();
  }, [text]);

  if (loading) {
    return <div className="panel" style={{ padding: "32px", textAlign: "center", color: "#859490" }}>Analyzing cognitive vocabulary progression...</div>;
  }

  if (!data.length || !analysis) {
    return null;
  }

  const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 5);
  if (sentences.length < 6 || analysis.verdict?.toUpperCase() === "INSUFFICIENT_DATA") {
    return (
      <div className="panel" style={{ marginTop: "24px", border: "1px solid rgba(255,255,255,0.1)" }}>
        <div style={{ padding: "32px", textAlign: "center", color: "#859490", display: "flex", flexDirection: "column", gap: "8px", alignItems: "center" }}>
          <span className="material-symbols-outlined" style={{ fontSize: "24px", opacity: 0.5 }}>warning</span>
          <span>Vocabulary curve requires 6+ sentences for reliable analysis</span>
        </div>
      </div>
    );
  }

  const isHuman = analysis.verdict === "human_curve" || analysis.verdict === "mixed_curve";
  const strokeColor = isHuman ? "#22c55e" : "#ef4444";
  const glowColor = isHuman ? "rgba(34, 197, 94, 0.4)" : "rgba(239, 68, 68, 0.4)";

  // Generate Reference Curves
  const refData = [
    { label: 1, ai: 0.60, human: 0.85 },
    { label: 2, ai: 0.62, human: 0.70 },
    { label: 3, ai: 0.58, human: 0.55 },
    { label: 4, ai: 0.61, human: 0.80 }, // Spike: new section
    { label: 5, ai: 0.59, human: 0.50 },
    { label: 6, ai: 0.60, human: 0.40 },
  ];

  return (
    <div className="panel" style={{ marginTop: "24px", border: `1px solid ${strokeColor}40` }}>
      <div style={{ padding: "20px 24px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px", color: "white" }}>
          <span style={{ 
            display: "inline-block", 
            width: "8px", 
            height: "8px", 
            borderRadius: "50%", 
            background: strokeColor,
            boxShadow: `0 0 10px ${glowColor}`
          }} />
          Vocabulary Novelty Analysis
        </h3>
        <p style={{ margin: "4px 0 0 0", fontSize: "14px", color: "#859490" }}>
          Analyzes how technical terminology is introduced. Humans build context progressively (curve with spikes). AI sprinkles terms uniformly (flat line).
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", padding: "24px" }}>
        {/* Actual Curve */}
        <div>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#dde4e0", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            This Document
          </h4>
          <div style={{ height: "200px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="label" stroke="#859490" tick={{fill: "#859490", fontSize: 11}} tickLine={false} />
                <YAxis domain={[0, 1]} stroke="#859490" tick={{fill: "#859490", fontSize: 11}} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ background: "#172033", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px" }}
                  itemStyle={{ color: "white" }}
                />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke={strokeColor} 
                  strokeWidth={3} 
                  dot={{ r: 4, fill: "#0c111c", stroke: strokeColor, strokeWidth: 2 }} 
                  activeDot={{ r: 6, fill: strokeColor }} 
                  animationDuration={1500}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", gap: "16px", marginTop: "16px", padding: "12px", background: "rgba(0,0,0,0.2)", borderRadius: "8px" }}>
            <div>
              <div style={{ fontSize: "11px", color: "#859490", textTransform: "uppercase" }}>Verdict</div>
              <div style={{ fontSize: "14px", fontWeight: "600", color: strokeColor }}>{analysis.verdict.replace("_", " ").toUpperCase()}</div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "#859490", textTransform: "uppercase" }}>Variance</div>
              <div style={{ fontSize: "14px", fontWeight: "600", color: "white" }}>{analysis.variance.toFixed(3)}</div>
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "#859490", textTransform: "uppercase" }}>Spikes</div>
              <div style={{ fontSize: "14px", fontWeight: "600", color: "white" }}>{analysis.spike_count}</div>
            </div>
          </div>
        </div>

        {/* Reference Curve */}
        <div>
          <h4 style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#dde4e0", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Reference Signatures
          </h4>
          <div style={{ height: "200px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={refData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="label" stroke="#859490" tick={{fill: "#859490", fontSize: 11}} tickLine={false} />
                <YAxis domain={[0, 1]} stroke="#859490" tick={{fill: "#859490", fontSize: 11}} tickLine={false} axisLine={false} />
                <Line type="monotone" name="AI (Uniform)" dataKey="ai" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                <Line type="monotone" name="Human (Progressive)" dataKey="human" stroke="#22c55e" strokeWidth={2} dot={false} />
                <Tooltip 
                  contentStyle={{ background: "#172033", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px" }}
                  itemStyle={{ color: "white" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div style={{ marginTop: "16px", fontSize: "13px", color: "#859490", lineHeight: 1.5 }}>
            <strong>The Insight:</strong> It is nearly impossible to prompt an LLM to generate a human-shaped vocabulary curve. They lack the cognitive architecture required to withhold terminology until context is built.
          </div>
        </div>
      </div>
    </div>
  );
}
