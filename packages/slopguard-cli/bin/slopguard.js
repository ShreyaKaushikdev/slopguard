#!/usr/bin/env node
/**
 * SlopGuard CLI — Node.js wrapper for the Python CLI.
 *
 * Usage:
 *   npx slopguard score "your text here"
 *   npx slopguard score --pr https://github.com/org/repo/pull/123
 *   npx slopguard score --file README.md --domain docs
 *   npx slopguard improve "your text here"
 *   npx slopguard batch ./samples.json
 *   npx slopguard evaluate
 *   npx slopguard hc3
 *
 * Requires Python 3.11+ with slopguard installed:
 *   pip install slopguard
 *
 * Or use a remote API:
 *   npx slopguard score "text" --api-url https://api.slopguard.dev
 */

const { spawnSync } = require("child_process");
const path = require("path");

const args = process.argv.slice(2);

// Check for --api-url to use remote API directly (no Python needed)
const apiUrlIndex = args.indexOf("--api-url");
const useRemoteApi = apiUrlIndex !== -1;

if (useRemoteApi) {
  // Use remote API directly with fetch
  const apiUrl = args[apiUrlIndex + 1];
  const command = args[0];
  const restArgs = args.slice(1).filter((a) => a !== "--api-url" && a !== apiUrl);

  handleRemoteApi(apiUrl, command, restArgs);
} else {
  // Use Python CLI
  const python = process.platform === "win32" ? "python" : "python3";

  // Try to find slopguard package
  const cliPath = path.join(__dirname, "..", "..", "apps", "api", "slopguard", "cli.py");

  const result = spawnSync(python, ["-m", "slopguard.cli", ...args], {
    stdio: "inherit",
    cwd: path.join(__dirname, "..", "..", "apps", "api"),
  });

  if (result.error) {
    if (result.error.code === "ENOENT") {
      console.error("Error: Python 3.11+ not found.");
      console.error("Install Python: https://www.python.org/downloads/");
      console.error();
      console.error("Or use a remote API:");
      console.error("  npx slopguard score 'text' --api-url https://api.slopguard.dev");
    } else {
      console.error(`Error: ${result.error.message}`);
    }
    process.exit(1);
  }

  process.exit(result.status || 0);
}

async function handleRemoteApi(apiUrl, command, args) {
  const baseUrl = apiUrl.replace(/\/+$/, "");

  let url, method, body;

  switch (command) {
    case "score": {
      url = `${baseUrl}/score/text`;
      const textIdx = args.findIndex((a) => !a.startsWith("--"));
      const text = textIdx !== -1 ? args[textIdx] : "";
      const domain = args.includes("--domain") ? args[args.indexOf("--domain") + 1] : "general";
      body = { text, domain };
      break;
    }
    case "improve": {
      url = `${baseUrl}/improve`;
      const textIdx = args.findIndex((a) => !a.startsWith("--"));
      const text = textIdx !== -1 ? args[textIdx] : "";
      const domain = args.includes("--domain") ? args[args.indexOf("--domain") + 1] : "general";
      body = { text, domain };
      break;
    }
    default:
      console.error(`Command "${command}" requires local Python installation.`);
      console.error("Install: pip install slopguard");
      process.exit(1);
  }

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    console.log(JSON.stringify(data, null, 2));
  } catch (err) {
    console.error(`Error: Could not reach API at ${url}: ${err.message}`);
    process.exit(1);
  }
}
