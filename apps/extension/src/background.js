async function getApiUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ apiUrl: "http://localhost:8000" }, ({ apiUrl }) => resolve(apiUrl));
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "SCORE_TEXT") {
    getApiUrl().then(base => {
      fetch(`${base}/score/text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request.payload)
      })
      .then(res => {
        if (!res.ok) throw new Error(`SlopGuard API ${res.status}`);
        return res.json();
      })
      .then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    });
    return true; // Keep message channel open for async response
  }
  
  if (request.type === "SCORE_PR") {
    getApiUrl().then(base => {
      fetch(`${base}/score/pr`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request.payload)
      })
      .then(res => {
        if (!res.ok) throw new Error(`SlopGuard API ${res.status}`);
        return res.json();
      })
      .then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    });
    return true;
  }
  
  if (request.type === "RECORD_EVENT") {
    getApiUrl().then(base => {
      fetch(`${base}/events/score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request.payload)
      })
      .then(res => {
        if (!res.ok) throw new Error(`SlopGuard API ${res.status}`);
        return res.json();
      })
      .then(data => sendResponse({ success: true, data }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    });
    return true;
  }
});
