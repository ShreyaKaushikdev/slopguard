const MIN_TEXT_LENGTH = 120;
const MAX_BLOCKS = 8;
const MAX_API_CALLS = 12;
const MAX_RESCANS = 5;
const DEBOUNCE_MS = 2000;

let apiCallCount = 0;
let rescanCount = 0;

function guessDomain() {
  const host = location.hostname;
  if (host.includes("github.com")) return "code_review";
  if (host.includes("amazon.") || host.includes("flipkart.")) return "marketplace";
  if (host.includes("linkedin.") || host.includes("twitter.") || host.includes("x.com") || host.includes("reddit.")) return "social_news";
  if (host.includes("arxiv.") || host.includes("scholar.google.")) return "academia";
  if (host.includes("notion.") || host.includes("confluence.") || host.includes("docs.")) return "docs";
  if (host.includes("mail.google.") || host.includes("outlook.")) return "communications";
  return "content";
}

function candidateBlocks(onlyNew = false) {
  const selectors = [
    ".markdown-body",
    "article",
    "[data-testid='review']",
    "[data-testid='tweetText']",
    ".feed-shared-update-v2",
    "main",
    "section"
  ];
  const seen = new Set();
  const blocks = [];
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      if (onlyNew && node.dataset.slopguardScored === "true") continue;
      const text = (node.innerText || "").trim();
      if (text.length < MIN_TEXT_LENGTH || seen.has(text.slice(0, 100))) continue;
      seen.add(text.slice(0, 100));
      blocks.push({ node, text });
      if (blocks.length >= MAX_BLOCKS) return blocks;
    }
  }
  return blocks;
}

function githubPrInfo() {
  if (!location.hostname.includes("github.com") || !/\/pull\/\d+/.test(location.pathname)) {
    return null;
  }
  const title =
    document.querySelector("bdi.js-issue-title")?.innerText?.trim() ||
    document.querySelector(".js-issue-title")?.innerText?.trim() ||
    document.title.replace(" by ", " ");
  const bodyNode =
    document.querySelector(".comment-body.markdown-body") ||
    document.querySelector(".js-comment-body .markdown-body") ||
    document.querySelector(".timeline-comment .markdown-body");
  const description = bodyNode?.innerText?.trim() || "";
  if (!description || description.length < 40) return null;
  return { node: bodyNode, title, description };
}

function colorFor(oversight) {
  if (oversight === "high") return "#16a34a";
  if (oversight === "mixed") return "#ca8a04";
  if (oversight === "low") return "#dc2626";
  return "#6b7280";
}

function oversightColorClass(oversight) {
  if (oversight === "high") return "#22c55e";
  if (oversight === "mixed") return "#eab308";
  if (oversight === "low") return "#ef4444";
  return "#94a3b8";
}

function signalBarGradient(score) {
  const pct = Math.round(score * 100);
  let color;
  if (score >= 0.65) color = "#22c55e";
  else if (score >= 0.4) color = "#eab308";
  else color = "#ef4444";
  return `linear-gradient(90deg, ${color} ${pct}%, #1e293b ${pct}%)`;
}

function attachBadge(node, result) {
  if (node.dataset.slopguardScored === "true") return;
  node.dataset.slopguardScored = "true";
  const badge = document.createElement("button");
  badge.className = "sg-badge";
  badge.style.background = colorFor(result.oversight);
  badge.textContent = `SG ${Math.round(result.score)}`;
  badge.title = result.summary;

  const detectedDomain = result.domain || guessDomain();
  const oversightColor = oversightColorClass(result.oversight);

  const panel = document.createElement("div");
  panel.className = "sg-panel";
  panel.innerHTML = `
    <div class="sg-panel-header">
      <strong>${result.summary}</strong>
      <span class="sg-panel-score">Score: <b>${result.score}</b>/100</span>
    </div>
    <div class="sg-panel-meta">
      <span class="sg-panel-domain">${detectedDomain.replace("_", " ")}</span>
      <span class="sg-panel-oversight" style="color:${oversightColor}">● ${result.oversight} oversight</span>
    </div>
    <div class="sg-signal-list">
      ${result.signals.slice(0, 5).map((s) => `
        <div class="sg-signal-row">
          <div class="sg-signal-info">
            <span class="sg-signal-name">${s.name}</span>
            <span class="sg-signal-pct">${Math.round(s.score * 100)}%</span>
          </div>
          <div class="sg-signal-bar" style="background:${signalBarGradient(s.score)}"></div>
          <span class="sg-signal-label">${s.label}</span>
        </div>
      `).join("")}
    </div>
    <a class="sg-dashboard-link" href="http://localhost:3000" target="_blank" rel="noopener">View in Dashboard →</a>
  `;
  panel.hidden = true;
  badge.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
  });

  const wrap = document.createElement("div");
  wrap.className = "sg-wrap";
  wrap.appendChild(badge);
  wrap.appendChild(panel);
  node.prepend(wrap);
}

async function recordScore(result, domain) {
  const event = {
    url: location.href,
    title: document.title,
    domain,
    score: result.score,
    oversight: result.oversight
  };
  chrome.storage.local.get({ slopguardHistory: [] }, ({ slopguardHistory }) => {
    const history = [event, ...slopguardHistory].slice(0, 100);
    chrome.storage.local.set({ slopguardHistory: history });
  });
  
  chrome.runtime.sendMessage({ type: "RECORD_EVENT", payload: event });
}

function checkRateLimit() {
  if (apiCallCount >= MAX_API_CALLS) {
    console.debug(`SlopGuard: rate limit reached (${MAX_API_CALLS} calls). Stopping scoring.`);
    return false;
  }
  apiCallCount++;
  return true;
}

async function scoreBlock(block, domain) {
  if (!checkRateLimit()) return null;
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      { type: "SCORE_TEXT", payload: { text: block.text.slice(0, 6000), domain } },
      (response) => {
        if (response && response.success) resolve(response.data);
        else reject(new Error(response?.error || "Background script failed"));
      }
    );
  });
}

async function scorePr(pr) {
  if (!checkRateLimit()) return null;
  let diff = "";
  try {
    const diffResponse = await fetch(`${location.origin}${location.pathname}.diff`);
    diff = diffResponse.ok ? await diffResponse.text() : "";
  } catch (error) {
    console.debug("SlopGuard diff fetch skipped", error);
  }
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      {
        type: "SCORE_PR",
        payload: {
          title: pr.title,
          description: pr.description.slice(0, 6000),
          diff: diff.slice(0, 12000),
          comments: []
        }
      },
      (response) => {
        if (response && response.success) resolve(response.data);
        else reject(new Error(response?.error || "Background script failed"));
      }
    );
  });
}

async function run(onlyNew = false) {
  const domain = guessDomain();

  if (!onlyNew) {
    const pr = githubPrInfo();
    if (pr) {
      try {
        const result = await scorePr(pr);
        if (result) {
          attachBadge(pr.node, result);
          await recordScore(result, "code_review");
        }
        return;
      } catch (error) {
        console.debug("SlopGuard PR scoring skipped", error);
      }
    }
  }

  for (const block of candidateBlocks(onlyNew)) {
    try {
      const result = await scoreBlock(block, domain);
      if (result) {
        attachBadge(block.node, result);
        await recordScore(result, domain);
      }
    } catch (error) {
      console.debug("SlopGuard scoring skipped", error);
    }
  }
}

// Initial run
run();

// MutationObserver for SPA support
let debounceTimer = null;

const observer = new MutationObserver(() => {
  if (rescanCount >= MAX_RESCANS) {
    observer.disconnect();
    console.debug("SlopGuard: max rescans reached, observer disconnected.");
    return;
  }
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    rescanCount++;
    console.debug(`SlopGuard: rescan #${rescanCount}`);
    run(true);
  }, DEBOUNCE_MS);
});

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
}
