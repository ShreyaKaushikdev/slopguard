#!/usr/bin/env python
"""SlopGuard GitHub Action — PR Check.

Scores PR descriptions and diffs for human oversight.
Posts inline annotations on low-quality content.
Posts a summary review comment on the PR.
Sets check status (pass/fail) based on configured threshold.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True, help="SlopGuard API URL")
    parser.add_argument("--min-score", type=int, default=60, help="Minimum score to pass")
    parser.add_argument("--fail-on", default="description_slop", help="Comma-separated fail conditions")
    parser.add_argument("--annotate-diff", default="true", help="Post inline annotations")
    parser.add_argument("--comment-summary", default="true", help="Post PR summary comment")
    parser.add_argument("--domain", default="code_review", help="Domain adapter")
    parser.add_argument("--github-token", required=True, help="GitHub token")
    parser.add_argument("--github-api-url", default="https://api.github.com", help="GitHub API URL")
    parser.add_argument("--repository", required=True, help="Owner/repo")
    parser.add_argument("--pr-number", default="", help="PR number")
    parser.add_argument("--sha", required=True, help="Commit SHA")
    return parser.parse_args()


def github_request(url: str, token: str, method: str = "GET", data: dict | None = None) -> Any:
    """Make an authenticated request to the GitHub API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "SlopGuard-Action/0.1",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return None
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"::warning::GitHub API error {e.code}: {e.read().decode()[:200]}")
        return None


def fetch_pr(api_url: str, token: str, repo: str, pr_number: str) -> dict | None:
    """Fetch PR metadata (title, body, diff)."""
    base = f"{api_url}/repos/{repo}"

    # Fetch PR details
    pr_data = github_request(f"{base}/pulls/{pr_number}", token)
    if not pr_data:
        return None

    # Fetch diff
    diff_data = github_request(f"{base}/pulls/{pr_number}.diff", token)
    diff_text = ""
    if diff_data and isinstance(diff_data, str):
        diff_text = diff_data
    elif diff_data and isinstance(diff_data, dict):
        diff_text = diff_data.get("diff", "")

    return {
        "title": pr_data.get("title", ""),
        "body": pr_data.get("body", ""),
        "diff": diff_text,
        "number": pr_data.get("number"),
        "author": pr_data.get("user", {}).get("login", ""),
        "additions": pr_data.get("additions", 0),
        "deletions": pr_data.get("deletions", 0),
    }


def score_pr(api_url: str, title: str, body: str, diff: str, domain: str) -> dict | None:
    """Score the PR using SlopGuard API."""
    # Try description + diff first
    url = f"{api_url}/score/pr"
    payload = {
        "title": title,
        "description": body or title,
        "diff": diff[:12000],
        "comments": [],
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"::warning::SlopGuard API error: {e}")
        return None


def parse_diff_files(diff: str) -> list[dict]:
    """Parse a unified diff to extract file paths and added lines."""
    files = []
    current_file = None
    current_line = 0

    for line in diff.splitlines():
        if line.startswith("--- a/"):
            current_file = None
        elif line.startswith("+++ b/"):
            current_file = {"path": line[6:], "added_lines": []}
            files.append(current_file)
            current_line = 0
        elif line.startswith("@@") and current_file:
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                current_line = int(match.group(1)) - 1
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            current_line += 1
            current_file["added_lines"].append({"line": current_line, "content": line[1:]})
        elif not line.startswith("-") and not line.startswith("\\") and current_line > 0:
            current_line += 1

    return files


def find_file_for_sentence(sentence: str, diff_files: list[dict]) -> tuple[str, int]:
    """Try to find which file a sentence's referenced identifier belongs to."""
    words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", sentence))
    for f in diff_files:
        for added in f["added_lines"]:
            line_words = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", added["content"]))
            if words & line_words:
                return f["path"], added["line"]
    return "", 0


def post_pr_comment(
    api_url: str,
    token: str,
    repo: str,
    pr_number: str,
    body: str,
) -> None:
    """Post a top-level review comment on the PR."""
    url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"
    payload = {"body": body}
    github_request(url, token, "POST", payload)


def extract_sentences(text: str) -> list[tuple[str, int, int]]:
    """Extract sentences with their character offsets."""
    sentences = []
    for match in re.finditer(r'[^.!?]+[.!?]*', text):
        sentence = match.group().strip()
        if len(sentence) > 10:
            sentences.append((sentence, match.start(), match.end()))
    return sentences


def find_diff_line_for_offset(diff: str, char_offset: int) -> int:
    """Approximate which diff line a character offset corresponds to."""
    lines = diff.splitlines()
    current_offset = 0
    for i, line in enumerate(lines):
        if current_offset >= char_offset:
            return i + 1
        current_offset += len(line) + 1  # +1 for newline
    return max(1, len(lines))


def post_inline_annotation(
    api_url: str,
    token: str,
    repo: str,
    pr_number: str,
    body_text: str,
    line: int,
    path: str = "",
    side: str = "RIGHT",
) -> None:
    """Post an inline review comment on the PR."""
    url = f"{api_url}/repos/{repo}/pulls/{pr_number}/comments"
    payload = {
        "body": body_text,
        "path": path or "PR description",
        "line": line,
        "side": side,
        "commit_id": None,  # Will be resolved by GitHub
    }
    # Use reviews API if we don't have a specific commit
    review_url = f"{api_url}/repos/{repo}/pulls/{pr_number}/reviews"
    review_payload = {
        "body": body_text,
        "event": "COMMENT",
        "comments": [{
            "path": path or "PR description",
            "line": line,
            "side": side,
            "body": body_text,
        }],
    }
    github_request(review_url, token, "POST", review_payload)


def create_check_run(
    api_url: str,
    token: str,
    repo: str,
    sha: str,
    name: str,
    conclusion: str,
    summary: str,
    annotations: list[dict],
) -> None:
    """Create a check run with the scoring results."""
    url = f"{api_url}/repos/{repo}/check-runs"
    payload = {
        "name": name,
        "head_sha": sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": f"SlopGuard Oversight Score",
            "summary": summary,
            "annotations": annotations[:50],  # GitHub limits to 50
        },
    }
    github_request(url, token, "POST", payload)


def set_output(name: str, value: str) -> None:
    """Set a GitHub Actions output variable."""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")


def build_pr_comment(score: int, oversight: str, min_score: int, passed: bool, fail_reasons: list[str], result: dict) -> str:
    """Build a PR summary comment markdown."""
    lines = [
        "## SlopGuard PR Check Report",
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| **Oversight Score** | `{score}/100` |",
        f"| **Oversight Level** | {oversight.title()} |",
        f"| **Threshold** | `{min_score}` |",
        f"| **Result** | {'PASS' if passed else 'FAIL'} |",
        "",
    ]

    why_signal = next((s for s in result.get("signals", []) if s.get("name") == "why_vs_what"), None)
    if why_signal:
        lines.append("### Reasoning Analysis")
        lines.append("")
        lines.append(f"- **Specificity Score:** {why_signal.get('specificity_score', 'N/A')}")
        lines.append(f"- **Reasoning Quality:** {why_signal.get('reasoning_quality', 'N/A')}")
        lines.append("")

        if why_signal.get("flagged_claims"):
            lines.append(f"⚠️ **{len(why_signal['flagged_claims'])} claim(s) need more specificity:**")
            lines.append("")
            for claim in why_signal["flagged_claims"][:5]:
                verdict = claim.get("verdict", "").replace("_", " ").title()
                sentence = claim.get("sentence", "")[:120]
                suggestion = claim.get("suggestion", "")
                lines.append(f"- **{verdict}:** `{sentence}`")
                if suggestion:
                    lines.append(f"  - {suggestion}")
            lines.append("")

        if why_signal.get("strong_claims"):
            lines.append(f"✅ **{len(why_signal['strong_claims'])} strong claim(s):**")
            lines.append("")
            for claim in why_signal["strong_claims"][:5]:
                sentence = claim.get("sentence", "")[:120]
                lines.append(f"- `{sentence}`")
            lines.append("")

    if fail_reasons:
        lines.append("### Fail Reasons")
        lines.append("")
        for reason in fail_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    lines.append("---")
    lines.append("*Powered by [SlopGuard](https://github.com/slopguard/slopguard)*")
    return "\n".join(lines)


def build_check_summary(score: int, oversight: str, min_score: int, passed: bool, fail_reasons: list[str], result: dict) -> str:
    """Build a check run summary markdown."""
    lines = [
        f"## SlopGuard PR Check",
        f"",
        f"**Score:** {score}/100",
        f"**Oversight:** {oversight.title()}",
        f"**Threshold:** {min_score}",
        f"**Result:** {'PASS' if passed else 'FAIL'}",
        f"",
    ]

    if fail_reasons:
        lines.append("### Fail Reasons")
        for reason in fail_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    why_signal = next((s for s in result.get("signals", []) if s.get("name") == "why_vs_what"), None)
    if why_signal:
        lines.append("### Reasoning Quality")
        lines.append(f"- **Specificity:** {why_signal.get('specificity_score', 'N/A')}")
        lines.append(f"- **Quality:** {why_signal.get('reasoning_quality', 'N/A')}")
        lines.append(f"- **Flagged claims:** {len(why_signal.get('flagged_claims', []))}")
        lines.append(f"- **Strong claims:** {len(why_signal.get('strong_claims', []))}")
        lines.append("")

        if why_signal.get("flagged_claims"):
            lines.append("### Flagged Claims")
            for claim in why_signal["flagged_claims"][:5]:
                lines.append(f"- **{claim.get('verdict', '').replace('_', ' ').title()}:** `{claim.get('sentence', '')[:100]}...`")
                if claim.get("suggestion"):
                    lines.append(f"  - Suggestion: {claim['suggestion']}")
            lines.append("")

        if why_signal.get("strong_claims"):
            lines.append("### Strong Claims")
            for claim in why_signal["strong_claims"][:5]:
                lines.append(f"- **{claim.get('verdict', '').replace('_', ' ').title()}:** `{claim.get('sentence', '')[:100]}...`")
            lines.append("")

    return "\n".join(lines)


def main():
    args = parse_args()
    fail_conditions = [c.strip() for c in args.fail_on.split(",")]
    annotate = args.annotate_diff.lower() == "true"
    comment_summary = args.comment_summary.lower() == "true"

    print(f"::group::Fetching PR #{args.pr_number}")
    pr = fetch_pr(args.github_api_url, args.github_token, args.repository, args.pr_number)
    if not pr:
        print("::error::Could not fetch PR data. Make sure GITHUB_TOKEN has read access.")
        sys.exit(1)

    title = pr["title"] or ""
    body = pr["body"] or ""
    diff = pr["diff"] or ""

    print(f"PR #{pr['number']} by {pr['author']}")
    print(f"Title: {title[:80]}...")
    print(f"Body length: {len(body)} chars")
    print(f"Diff length: {len(diff)} chars")
    print("::endgroup::")

    # Parse diff for file-aware annotations
    diff_files = parse_diff_files(diff) if diff else []

    # Score the PR
    print(f"::group::Scoring with SlopGuard")
    result = score_pr(args.api_url, title, body, diff, args.domain)
    if not result:
        print("::error::Could not reach SlopGuard API. Check API_URL.")
        sys.exit(1)

    score = result.get("score", 0)
    oversight = result.get("oversight", "unknown")
    print(f"Score: {score}/100")
    print(f"Oversight: {oversight}")
    print("::endgroup::")

    # Set outputs
    set_output("score", str(score))
    set_output("oversight", oversight)

    # Extract flagged claims for output
    flagged = []
    for signal in result.get("signals", []):
        if signal.get("flagged_claims"):
            flagged.extend(signal["flagged_claims"])
    set_output("flagged_claims", json.dumps(flagged))

    # Determine pass/fail
    passed = score >= args.min_score
    fail_reasons = []

    if score < args.min_score and "description_slop" in fail_conditions:
        fail_reasons.append(f"Score {score} below minimum {args.min_score}")

    # Check for rubber-stamp reviews
    if "rubber_stamp" in fail_conditions:
        for signal in result.get("signals", []):
            if signal.get("name") == "reviewer_impact_proxy" and signal.get("score", 1) < 0.3:
                fail_reasons.append("Low reviewer impact detected (rubber-stamp)")

    # Check for low comment intelligence
    if "low_comment_intelligence" in fail_conditions:
        for signal in result.get("signals", []):
            if signal.get("name") == "code_comment_intelligence" and signal.get("score", 1) < 0.4:
                fail_reasons.append("Code comments lack intelligence (restating code)")

    if fail_reasons:
        passed = False

    # Post inline annotations
    annotations = []
    if annotate and body:
        print(f"::group::Posting inline annotations")
        sentences = extract_sentences(body)
        why_signal = next((s for s in result.get("signals", []) if s.get("name") == "why_vs_what"), None)

        if why_signal and why_signal.get("flagged_claims"):
            for claim in why_signal["flagged_claims"]:
                claim_text = claim.get("sentence", "")
                # Try to find the sentence in a diff file first
                file_path, file_line = find_file_for_sentence(claim_text, diff_files)

                if file_path and file_line:
                    # Post inline on the actual code file
                    annotation_body = (
                        f"**SlopGuard: {claim.get('verdict', 'low_quality').replace('_', ' ').title()}**\n\n"
                        f"{claim.get('suggestion', 'Consider adding more specific details.')}\n\n"
                        f"*Specificity: {claim.get('specificity', 0):.2f}*"
                    )
                    post_inline_annotation(
                        args.github_api_url,
                        args.github_token,
                        args.repository,
                        args.pr_number,
                        annotation_body,
                        file_line,
                        file_path,
                    )
                    annotations.append({
                        "path": file_path,
                        "start_line": file_line,
                        "end_line": file_line,
                        "annotation_level": "warning",
                        "message": f"SlopGuard: {claim.get('suggestion', 'Low specificity')}",
                    })
                    print(f"::warning file={file_path},line={file_line}::{claim.get('suggestion', 'Low specificity')}")
                else:
                    # Fall back to PR description annotations
                    for sent_text, start, end in sentences:
                        if claim_text[:30] in sent_text or sent_text[:30] in claim_text:
                            line_num = find_diff_line_for_offset(body, start)
                            annotation_body = (
                                f"**SlopGuard: {claim.get('verdict', 'low_quality').replace('_', ' ').title()}**\n\n"
                                f"{claim.get('suggestion', 'Consider adding more specific details.')}\n\n"
                                f"*Specificity: {claim.get('specificity', 0):.2f}*"
                            )
                            if args.pr_number:
                                post_inline_annotation(
                                    args.github_api_url,
                                    args.github_token,
                                    args.repository,
                                    args.pr_number,
                                    annotation_body,
                                    line_num,
                                )
                            annotations.append({
                                "path": "PR description",
                                "start_line": line_num,
                                "end_line": line_num,
                                "annotation_level": "warning",
                                "message": f"SlopGuard: {claim.get('suggestion', 'Low specificity')}",
                            })
                            print(f"::warning file=PR description,line={line_num}::{claim.get('suggestion', 'Low specificity')}")
                            break

        # Summary annotations
        if not passed:
            annotations.append({
                "path": "PR description",
                "start_line": 1,
                "end_line": 1,
                "annotation_level": "failure" if score < args.min_score * 0.7 else "warning",
                "message": f"Oversight score {score}/100 is below minimum {args.min_score}. {oversight.title()} oversight detected.",
            })

        print("::endgroup::")

    # Post PR summary comment
    if comment_summary and args.pr_number:
        print(f"::group::Posting PR summary comment")
        summary_comment = build_pr_comment(score, oversight, args.min_score, passed, fail_reasons, result)
        post_pr_comment(
            args.github_api_url,
            args.github_token,
            args.repository,
            args.pr_number,
            summary_comment,
        )
        print("::endgroup::")

    # Create check run
    conclusion = "success" if passed else "failure"
    summary_text = build_check_summary(score, oversight, args.min_score, passed, fail_reasons, result)

    create_check_run(
        args.github_api_url,
        args.github_token,
        args.repository,
        args.sha,
        "slopguard/pr-check",
        conclusion,
        summary_text,
        annotations,
    )

    # Print summary to actions log
    print(f"\n::group::SlopGuard Summary")
    print(summary_text)
    print("::endgroup::")

    # Exit with appropriate code
    if not passed:
        print(f"\n::error::SlopGuard check failed: {'; '.join(fail_reasons)}")
        sys.exit(1)
    else:
        print(f"\nSlopGuard check passed (score {score} >= {args.min_score})")
        sys.exit(0)


if __name__ == "__main__":
    main()
