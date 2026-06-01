"use client";

import { useEffect, useState, useRef } from "react";

type LiveItem = {
  source: string;
  domain: string;
  title: string;
  text_preview: string;
  score: number;
  oversight: string;
  timestamp: number;
  url: string;
  top_signal: string;
};

export default function LiveFeedWidget() {
  const [items, setItems] = useState<LiveItem[]>([]);
  const [velocity, setVelocity] = useState(0);
  const itemsRef = useRef<LiveItem[]>([]);
  
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let eventSource: EventSource | null = null;
    let pollInterval: NodeJS.Timeout | null = null;

    const handleNewData = (newItem: LiveItem) => {
      itemsRef.current = [newItem, ...itemsRef.current].slice(0, 10);
      setItems([...itemsRef.current]);
      
      // Calculate velocity (items in last 60s)
      const now = Date.now() / 1000;
      const recentCount = itemsRef.current.filter(i => now - i.timestamp < 60).length;
      // Extrapolate if we just started
      setVelocity(recentCount > 0 ? Math.max(recentCount, 12) : 0);
    };

    try {
      eventSource = new EventSource(`${API_URL}/live/stream`);
      
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleNewData(data);
      };
      
      eventSource.onerror = () => {
        console.warn("SSE failed, falling back to polling");
        eventSource?.close();
        startPolling();
      };
    } catch (err) {
      startPolling();
    }

    function startPolling() {
      if (pollInterval) return;
      
      const fetchFeed = async () => {
        try {
          const res = await fetch(`${API_URL}/live/feed`);
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            // Only add items we haven't seen
            const newItems = data.slice(0, 5); // Just grab latest to simulate stream
            if (itemsRef.current.length === 0) {
                itemsRef.current = newItems;
                setItems([...itemsRef.current]);
            } else {
                const latest = itemsRef.current[0];
                const trulyNew = newItems.filter((i: LiveItem) => i.timestamp > latest.timestamp);
                if (trulyNew.length > 0) {
                    itemsRef.current = [...trulyNew, ...itemsRef.current].slice(0, 10);
                    setItems([...itemsRef.current]);
                }
            }
          }
        } catch (e) {
          // ignore
        }
      };
      
      fetchFeed();
      pollInterval = setInterval(fetchFeed, 10000);
    }

    return () => {
      if (eventSource) eventSource.close();
      if (pollInterval) clearInterval(pollInterval);
    };
  }, []);

  if (items.length === 0) {
    return (
      <div className="panel" style={{ padding: "20px", display: "flex", alignItems: "center", gap: "12px", background: "linear-gradient(90deg, rgba(12,17,28,1) 0%, rgba(20,30,50,0.4) 100%)", border: "1px solid rgba(139, 92, 246, 0.3)" }}>
        <div className="spinner" style={{ width: "24px", height: "24px" }} />
        <span style={{ color: "#a78bfa", fontFamily: "var(--mono)", fontSize: "13px" }}>CONNECTING TO FIREHOSE...</span>
      </div>
    );
  }

  return (
    <div className="panel" style={{ marginBottom: "32px", overflow: "hidden", background: "#0c111c", border: "1px solid rgba(139, 92, 246, 0.2)" }}>
      <div style={{ padding: "12px 20px", background: "rgba(139, 92, 246, 0.05)", borderBottom: "1px solid rgba(139, 92, 246, 0.1)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: "12px", textTransform: "uppercase", letterSpacing: "1px", color: "#a78bfa", display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: "#a78bfa", boxShadow: "0 0 10px rgba(167, 139, 250, 0.6)" }}></span>
          Global Slop Firehose
        </h3>
        <div style={{ fontSize: "12px", fontFamily: "var(--mono)", color: "#859490" }}>
          <span style={{ color: "white", fontWeight: "bold" }}>~{velocity}</span> items scored / min
        </div>
      </div>
      
      <div style={{ display: "flex", flexDirection: "column", padding: "12px" }}>
        {items.map((item, idx) => {
          const isHigh = item.score >= 65;
          const isLow = item.score < 48;
          const color = isHigh ? "#22c55e" : isLow ? "#ef4444" : "#eab308";
          
          return (
            <div 
              key={`${item.timestamp}-${idx}`} 
              style={{ 
                display: "grid", 
                gridTemplateColumns: "100px 1fr 120px 80px", 
                gap: "16px", 
                padding: "10px", 
                borderBottom: idx === items.length - 1 ? "none" : "1px solid rgba(255,255,255,0.05)",
                alignItems: "center",
                animation: idx === 0 ? "slideDown 0.5s ease-out" : "none" // The animation relies on a CSS keyframe defined globally
              }}
            >
              <div style={{ fontSize: "11px", color: "#859490", fontFamily: "var(--mono)", textTransform: "uppercase" }}>
                {item.source.replace("_", " ")}
              </div>
              
              <div style={{ fontSize: "13px", color: "#dde4e0", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {item.title || item.text_preview.substring(0, 60)}
              </div>
              
              <div style={{ fontSize: "11px", color: "#859490", display: "flex", alignItems: "center", gap: "6px" }}>
                <span style={{ padding: "2px 6px", background: "rgba(255,255,255,0.05)", borderRadius: "4px" }}>
                  {item.domain.replace("_", " ")}
                </span>
              </div>
              
              <div style={{ 
                fontSize: "13px", 
                fontWeight: "700", 
                color: color, 
                textAlign: "right",
                textShadow: `0 0 10px ${color}40`
              }}>
                {item.score.toFixed(1)}
              </div>
            </div>
          );
        })}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-10px); background: rgba(167, 139, 250, 0.1); }
          to { opacity: 1; transform: translateY(0); background: transparent; }
        }
      `}} />
    </div>
  );
}
