# Slack Bot Integration

The SlopGuard API can be used by a Slack bot whenever someone shares a long
message or article link.

```ts
app.message(async ({ message, say }) => {
  const text = message.text ?? "";
  if (text.length < 160) return;

  const result = await fetch(`${process.env.SLOPGUARD_API_URL}/score/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, domain: "communications" }),
  }).then((res) => res.json());

  if (result.oversight === "low") {
    await say({
      thread_ts: message.ts,
      text: `SlopGuard: low oversight signal (${result.score}/100). ${result.summary}`,
    });
  }
});
```
