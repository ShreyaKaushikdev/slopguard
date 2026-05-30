# Contributing to SlopGuard

SlopGuard detects missing human oversight, not AI authorship. Contributions
should keep that line clear.

## Local Setup

Run the API:

```powershell
cd apps/api
pip install -r requirements.txt
uvicorn slopguard.main:app --reload --port 8000
```

Run the dashboard:

```powershell
cd apps/web
npm install
npm run dev
```

Load the extension from `apps/extension` in Chrome developer mode.

## Adding a Signal

1. Add explainable signal logic in `apps/api/slopguard/detectors`.
2. Return a `SignalResult` with a clear `reason`.
3. Add or update samples in `datasets/samples/slopguard_samples.json`.
4. Add a test when the signal changes scoring behavior.

## Signal Rules

- Prefer evidence that maps to human judgment: reasoning, specificity, examples,
  decisions, risks, corrections, citations, or source grounding.
- Do not flag content only because it uses one word or punctuation style.
- Do not claim proof of AI generation.
- Every score must be explainable to a human reviewer.

## Pull Request Checklist

- `python -m pytest` passes in `apps/api`.
- `npm run build` passes in `apps/web`.
- README or docs are updated if behavior changes.
- New detection behavior includes at least one sample.
