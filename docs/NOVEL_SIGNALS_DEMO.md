# Novel Signals Demo Script — Sharpest Signal Prize

This demo showcases the three novel detection signals that make SlopGuard untouchable. Each signal catches patterns that are **hard to fake** and **impossible to ignore**.

---

## Setup

```bash
# Start the API
cd apps/api
uvicorn slopguard.main:app --reload --port 8000

# In another terminal, follow along with these curl commands
```

---

## Signal 1: Epistemic Cowardice Detector

**The insight:** AI systematically avoids taking positions. It hedges everything. It presents "both sides." It never commits to a recommendation.

### Demo 1A: Cowardly Text (AI-generated)

```bash
curl -X POST http://localhost:8000/signals/epistemic-cowardice \
  -H "Content-Type: application/json" \
  -d '{
    "text": "You might want to consider using Redis for caching, depending on your use case. It could potentially improve performance in some scenarios, though results may vary. Some developers believe it'\''s better than Memcached, but others prefer different solutions. Your mileage may vary. It depends on your specific requirements. Consult an expert for your particular situation.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "verdict": "cowardly",
  "score": 0.15,
  "hedge_density": 8.5,
  "hedge_clustering": 6,
  "opinion_laundering_count": 2,
  "commitment_count": 0,
  "responsibility_deflection": 1,
  "explanation": "Epistemic cowardice: hedging without commitment, false balance without resolution."
}
```

**What to point out to judges:**
- Hedge density of 8.5% (6 hedges in one paragraph)
- Opinion laundering: "some developers believe"
- Responsibility deflection: "consult an expert" as conclusion
- Zero commitments: no falsifiable predictions
- **Score: 0.15 — this is epistemic cowardice**

### Demo 1B: Committed Text (Human expert)

```bash
curl -X POST http://localhost:8000/signals/epistemic-cowardice \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Don'\''t use moment.js for new projects. It'\''s deprecated and the bundle size is 67kb minified. Use date-fns instead — it'\''s tree-shakeable and you only pay for what you use. I recommend date-fns for all new projects. This will reduce your bundle size by at least 40kb in most cases.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "verdict": "committed",
  "score": 0.82,
  "hedge_density": 0.0,
  "commitment_count": 3,
  "explanation": "Strong commitment: definitive recommendations with minimal hedging."
}
```

**What to point out to judges:**
- Three definitive commitments: "Don't use", "Use instead", "I recommend"
- Specific numbers: 67kb, 40kb
- Falsifiable prediction: "will reduce your bundle size by at least 40kb"
- **Score: 0.82 — this is how experts write**

**The key insight:** You cannot prompt-engineer commitment. To score well, you have to actually take a position. AI systems are trained to be helpful to everyone, which means committing to nothing.

---

## Signal 2: Counterfactual Absence Detector

**The insight:** When humans actually think, they consider what could go wrong, what alternatives they rejected, and why. AI generates the happy path and nothing else.

### Demo 2A: Counterfactual Absence (AI-generated)

```bash
curl -X POST http://localhost:8000/signals/counterfactual-absence \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Implemented caching to improve performance. The new system is more robust and follows best practices. This enhances the user experience and provides better scalability. The implementation is optimized for high throughput.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "verdict": "counterfactual_absence",
  "score": 0.0,
  "rejected_alternatives": 0,
  "failure_modes": 0,
  "specific_conditions": 0,
  "specific_tradeoffs": 0,
  "pure_positive_complex": true,
  "explanation": "Complex topic with zero caveats, failure modes, or alternatives mentioned — pure happy path."
}
```

**What to point out to judges:**
- Zero alternatives mentioned
- Zero failure modes discussed
- Zero tradeoffs acknowledged
- Pure positive framing on a complex topic (caching, scalability)
- **Score: 0.0 — this is the happy path, not real thinking**

### Demo 2B: Rich Counterfactuals (Human expert)

```bash
curl -X POST http://localhost:8000/signals/counterfactual-absence \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Fixed JWT secret exposure in auth/middleware.js. Previously, the implementation logged the full token on line 47, appearing in CloudWatch logs. Considered using environment variables but rejected that approach because our deployment pipeline doesn'\''t support secret rotation. Instead, switched to AWS Secrets Manager with automatic rotation. This breaks if the Secrets Manager API is unavailable, so added a 5-second timeout with fallback to cached credentials. Trading 20ms latency for automatic secret rotation is worth it. Edge case: if the cache is empty AND Secrets Manager is down, authentication will fail. We'\''ve accepted this risk because it'\''s better than logging secrets.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "verdict": "rich_counterfactuals",
  "score": 0.72,
  "rejected_alternatives": 2,
  "failure_modes": 2,
  "specific_conditions": 1,
  "specific_tradeoffs": 1,
  "specificity_ratio": 1.0,
  "explanation": "Rich counterfactual reasoning: specific alternatives rejected, failure modes identified, tradeoffs quantified."
}
```

**What to point out to judges:**
- Rejected alternative: "Considered environment variables but rejected because..."
- Explicit failure modes: "This breaks if...", "Edge case: if..."
- Specific tradeoff: "Trading 20ms latency for automatic secret rotation"
- Risk acknowledgment: "We've accepted this risk because..."
- **Score: 0.72 — this is how real engineers document decisions**

**The key insight:** Generic counterfactuals are easy to prompt-engineer ("may have performance implications"). Specific counterfactuals require domain knowledge ("breaks when queue depth exceeds 10k messages because Redis pub/sub doesn't buffer").

---

## Signal 3: Vocabulary Novelty Collapse Detector

**The insight:** Human experts introduce concepts progressively. AI distributes terminology uniformly. This signal looks at the SHAPE of vocabulary introduction, not the content.

### Demo 3A: Flat Curve (AI-generated)

```bash
curl -X POST http://localhost:8000/signals/vocabulary-novelty \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Authentication middleware validates JWT tokens using jsonwebtoken library. Token validation ensures user_id and role claims are present. Middleware returns 401 for invalid tokens with WWW-Authenticate header. JWT verification uses HS256 algorithm for signature validation. Token expiration checking prevents stale credential usage. Authentication flow integrates with authorization middleware for role-based access control.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "verdict": "flat_curve",
  "score": 0.28,
  "analysis": {
    "variance": 0.024,
    "slope": -0.003,
    "spike_count": 0,
    "entropy": 0.85,
    "front_loading": false
  },
  "curve": [0.92, 0.71, 0.67, 0.63, 0.58, 0.54],
  "explanation": "Low variance in vocabulary novelty: terms introduced uniformly rather than progressively."
}
```

**What to point out to judges:**
- Low variance (0.024): novelty is uniform across sentences
- Near-zero slope (-0.003): no progressive building
- Zero spikes: no section transitions
- **The curve is flat — AI distributes technical terms uniformly**

### Demo 3B: Human Curve (Progressive building)

```bash
curl -X POST http://localhost:8000/signals/vocabulary-novelty \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Authentication is critical for web applications. Users need secure access. We implemented JWT-based authentication using the jsonwebtoken library. The token contains user_id, role, and expiration timestamp encoded with HS256 algorithm. Token validation happens in middleware/auth.js using the verify() method. Invalid tokens return 401 Unauthorized with WWW-Authenticate header. Edge cases include expired tokens, malformed payloads, and signature mismatches. Each case has specific error handling with appropriate HTTP status codes and error messages.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "verdict": "human_curve",
  "score": 0.74,
  "analysis": {
    "variance": 0.089,
    "slope": -0.042,
    "spike_count": 2,
    "entropy": 1.68,
    "front_loading": false
  },
  "curve": [1.0, 0.83, 0.71, 0.54, 0.42, 0.38, 0.67, 0.45],
  "explanation": "Human vocabulary curve: decreasing novelty with section spikes indicates progressive concept building."
}
```

**What to point out to judges:**
- High variance (0.089): novelty varies significantly
- Negative slope (-0.042): novelty decreases as context builds
- Two spikes: section transitions (general → implementation → edge cases)
- **The curve has shape — human experts build context progressively**

**Visualization moment:** If you have a chart, plot both curves side by side:
- AI curve: flat line around 0.6-0.7
- Human curve: starts high (1.0), decreases, spikes at transitions

**The key insight:** This is the most technically sophisticated signal. It's looking at the cognitive process that generated the text, not the content itself. You cannot prompt-engineer a human-shaped vocabulary novelty curve.

---

## Combined Demo: All Three Signals on Real PR

```bash
curl -X POST http://localhost:8000/score/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Fixed JWT secret exposure in auth/middleware.js — previous implementation logged the full token on line 47, appearing in CloudWatch logs. I considered using environment variables but rejected that approach because our deployment pipeline doesn'\''t support secret rotation. Instead, I switched to AWS Secrets Manager with automatic rotation every 30 days. This breaks if the Secrets Manager API is unavailable, so I added a 5-second timeout with fallback to cached credentials. The tradeoff is 20ms additional latency on cold starts, but we gain automatic secret rotation and audit logging. Don'\''t use environment variables for secrets in production. Use a proper secret management service. This is non-negotiable for PCI compliance.",
    "domain": "code_review"
  }'
```

**Expected output:**
```json
{
  "score": 68.5,
  "oversight": "high",
  "signals": [
    {"name": "epistemic_cowardice", "score": 0.74, "weight": 1.5},
    {"name": "counterfactual_absence", "score": 0.78, "weight": 1.8},
    {"name": "vocabulary_novelty", "score": 0.71, "weight": 1.6},
    ...
  ]
}
```

**What to point out to judges:**
- All three novel signals score high (0.71-0.78)
- Combined weight: 4.9 (nearly 50% of total signal weight)
- Overall score: 68.5 (high oversight)
- **This is what genuine human thinking looks like**

---

## Why These Signals Win Sharpest Signal Prize

### 1. Technically Original
- **Epistemic Cowardice**: First detector to measure systematic position avoidance
- **Counterfactual Absence**: First to distinguish generic vs specific counterfactuals
- **Vocabulary Novelty**: First to analyze the SHAPE of vocabulary introduction curves

### 2. Hard to Fake
- **Epistemic Cowardice**: Requires actual commitment, not just removing hedge words
- **Counterfactual Absence**: Generic counterfactuals are easy, specific ones require domain knowledge
- **Vocabulary Novelty**: Cannot prompt-engineer a progressive vocabulary curve

### 3. Impossible to Ignore
- **Epistemic Cowardice**: Visually obvious (hedge clustering, false balance)
- **Counterfactual Absence**: Judges from Microsoft/Google/Amazon recognize real engineering decisions
- **Vocabulary Novelty**: Curve visualization is striking — flat line vs declining curve with spikes

### 4. Publishable Research
- **Vocabulary Novelty** in particular is a legitimate NLP research contribution
- No existing detector uses vocabulary novelty curve shape
- Could be published in ACL, EMNLP, or similar venues

---

## Talking Points for Judges

**"Why are these signals better than existing detectors?"**

Existing detectors ask "was this AI-generated?" We ask "did a human actually think about this?" That's a fundamentally different question. These three signals catch patterns that are invisible to traditional detectors:

1. **Epistemic Cowardice** catches AI's systematic avoidance of commitment
2. **Counterfactual Absence** catches AI's happy-path-only thinking
3. **Vocabulary Novelty** catches AI's uniform terminology distribution

**"Can these be gamed?"**

No. To game these signals, you'd need to:
1. Actually take a position and commit to it (epistemic cowardice)
2. Actually know what could go wrong with your implementation (counterfactual absence)
3. Actually build an argument progressively (vocabulary novelty)

At that point, you're not gaming the detector — you're doing the work.

**"What's the most impressive signal?"**

**Vocabulary Novelty** is the most technically sophisticated and the most publishable. It's analyzing the cognitive process that generated the text, not the content itself. No other detector does this.

**Counterfactual Absence** is the most immediately useful for code review. It catches the difference between "I updated the code" and "I considered X, rejected it because Y, chose Z, which breaks if W."

**Epistemic Cowardice** is the most visually obvious. Judges can see hedge clustering and false balance without technical explanation.

**All three together make SlopGuard untouchable.**

---

## Quick Demo Flow (5 minutes)

1. **Epistemic Cowardice** (1 min)
   - Show cowardly text → score 0.15
   - Show committed text → score 0.82
   - Point out: "You can't fake commitment"

2. **Counterfactual Absence** (2 min)
   - Show happy path → score 0.0
   - Show rich counterfactuals → score 0.72
   - Point out: "AI generates what works, humans think about what breaks"

3. **Vocabulary Novelty** (2 min)
   - Show flat curve → score 0.28
   - Show human curve → score 0.74
   - Visualize both curves side by side
   - Point out: "This is the shape of thinking"

**Total time: 5 minutes**
**Impact: Judges understand immediately why these signals are novel and hard to fake**
