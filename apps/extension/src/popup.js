const input = document.getElementById("apiUrl");
const status = document.getElementById("status");

chrome.storage.sync.get({ apiUrl: "http://localhost:8000" }, ({ apiUrl }) => {
  input.value = apiUrl;
});

document.getElementById("save").addEventListener("click", async () => {
  await chrome.storage.sync.set({ apiUrl: input.value.replace(/\/$/, "") });
  status.textContent = "Saved.";
});

chrome.storage.local.get({ slopguardHistory: [] }, ({ slopguardHistory }) => {
  // Today's stats
  const today = new Date().toDateString();
  const todayItems = slopguardHistory.filter((item) => {
    // history items don't have timestamps, so count all recent as "today"
    return true;
  });

  // Get current tab domain for domain-specific average
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentUrl = tabs[0]?.url || "";
    let currentHost = "";
    try { currentHost = new URL(currentUrl).hostname; } catch (e) {}

    const domainItems = slopguardHistory.filter((item) => {
      try { return new URL(item.url).hostname === currentHost; } catch (e) { return false; }
    });

    const statsTarget = document.getElementById("todayStats");
    if (statsTarget) {
      const pagesScored = Math.min(slopguardHistory.length, 100);
      const avgScore = domainItems.length > 0
        ? Math.round(domainItems.reduce((sum, item) => sum + item.score, 0) / domainItems.length)
        : "--";

      statsTarget.innerHTML = `
        <div class="sg-stats-grid">
          <div class="sg-stat-card">
            <span class="sg-stat-value">${pagesScored}</span>
            <span class="sg-stat-label">Pages Scored</span>
          </div>
          <div class="sg-stat-card">
            <span class="sg-stat-value">${avgScore}</span>
            <span class="sg-stat-label">Domain Avg</span>
          </div>
        </div>
      `;
    }
  });

  // Recent history
  const target = document.getElementById("history");
  target.innerHTML = slopguardHistory.slice(0, 5).map((item) => `
    <div class="sg-history-item">
      <div class="history-score">${Math.round(item.score)}</div>
      <div class="history-details">
        <span class="history-domain">${item.domain} &mdash; ${item.oversight}</span>
        <span class="history-title">${item.title || item.url}</span>
      </div>
    </div>
  `).join("") || "<p style='font-size:11px; color:#859490'>No scores yet.</p>";
});
