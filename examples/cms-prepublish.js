async function scoreBeforePublish(articleText) {
  const response = await fetch("http://localhost:8000/score/text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: articleText, domain: "content" }),
  });
  const result = await response.json();
  if (result.score < 48) {
    throw new Error(`SlopGuard blocked publish: ${result.summary}`);
  }
  return result;
}

module.exports = { scoreBeforePublish };
