#!/bin/bash
set -e

echo "=== SlopGuard PR Check ==="
echo "API URL: ${INPUT_API_URL}"
echo "Min Score: ${INPUT_MIN_SCORE}"
echo "Fail On: ${INPUT_FAIL_ON}"
echo "Annotate Diff: ${INPUT_ANNOTATE_DIFF}"
echo "Domain: ${INPUT_DOMAIN}"

python /pr_check.py \
  --api-url "${INPUT_API_URL}" \
  --min-score "${INPUT_MIN_SCORE}" \
  --fail-on "${INPUT_FAIL_ON}" \
  --annotate-diff "${INPUT_ANNOTATE_DIFF}" \
  --comment-summary "${INPUT_COMMENT_SUMMARY}" \
  --domain "${INPUT_DOMAIN}" \
  --github-token "${INPUT_GITHUB_TOKEN}" \
  --github-api-url "${GITHUB_API_URL:-https://api.github.com}" \
  --repository "${GITHUB_REPOSITORY}" \
  --pr-number "${GITHUB_EVENT_PATH:+$(cat $GITHUB_EVENT_PATH | python -c 'import sys,json; print(json.load(sys.stdin).get("pull_request",{}).get("number",""))' 2>/dev/null || echo '')}" \
  --sha "${GITHUB_SHA}"
