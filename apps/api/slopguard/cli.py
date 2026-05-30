import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from slopguard.evaluate import _find_samples_path, evaluate
from slopguard.models import TextScoreRequest
from slopguard.scoring import score_batch, score_text


def _api_request(url: str, data: dict) -> dict:
    """Make a request to the SlopGuard API."""
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error: API returned {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Could not reach API at {url}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(prog="slopguard", description="Score content for human oversight signals.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Score command
    score_parser = subparsers.add_parser("score", help="Score a single text string or file.")
    score_parser.add_argument("input", help="Text to score, or a file path when --file is set.")
    score_parser.add_argument("--file", action="store_true", help="Read input from a file path.")
    score_parser.add_argument("--domain", default="general", help="Domain adapter to use.")
    score_parser.add_argument("--pr", default="", help="Score a GitHub PR URL directly.")
    score_parser.add_argument("--api-url", default="", help="Use remote API instead of local scoring.")

    # Improve command
    improve_parser = subparsers.add_parser("improve", help="Get improvement suggestions for flagged text.")
    improve_parser.add_argument("input", help="Text to analyze for improvements.")
    improve_parser.add_argument("--file", action="store_true", help="Read input from a file path.")
    improve_parser.add_argument("--domain", default="general", help="Domain adapter to use.")
    improve_parser.add_argument("--api-url", default="", help="Use remote API.")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Score a JSON array of text items.")
    batch_parser.add_argument("path", help="Path to a JSON file with text/domain objects.")
    batch_parser.add_argument("--api-url", default="", help="Use remote API.")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a labeled sample dataset.")
    eval_parser.add_argument("path", nargs="?", default="", help="Path to labeled JSON samples.")

    # HC3 command
    hc3_parser = subparsers.add_parser("hc3", help="Run HC3 benchmark evaluation.")
    hc3_parser.add_argument("--domain", default="all", help="HC3 domain to evaluate.")
    hc3_parser.add_argument("--fast", action="store_true", help="Use fast subset.")

    # Live command
    live_parser = subparsers.add_parser("live", help="Show live feed from the running API.")
    live_parser.add_argument("--api-url", default="http://localhost:8000", help="API URL.")
    live_parser.add_argument("--limit", type=int, default=10, help="Number of items to show.")
    live_parser.add_argument("--worst", action="store_true", help="Show worst-scoring items only.")
    live_parser.add_argument("--stats", action="store_true", help="Show ingestion stats only.")
    live_parser.add_argument("--leaderboard", action="store_true", help="Show source leaderboard.")

    # Build dataset command
    build_parser = subparsers.add_parser("build-dataset", help="Build evaluation dataset from live sources.")
    build_parser.add_argument("--output", default="datasets/samples/full_dataset.json")
    build_parser.add_argument("--evaluate", action="store_true", help="Run evaluation after building.")
    build_parser.add_argument("--token", default="", help="GitHub token for higher rate limits.")

    args = parser.parse_args()

    if args.command == "score":
        if args.pr:
            # Score a GitHub PR URL via API
            api_url = args.api_url.rstrip("/") if args.api_url else "http://localhost:8000"
            result = _api_request(f"{api_url}/score/pr-url", {"url": args.pr})
            print(json.dumps(result, indent=2))
            return 0

        text = Path(args.input).read_text(encoding="utf-8") if args.file else args.input

        if args.api_url:
            # Use remote API
            api_url = args.api_url.rstrip("/")
            result = _api_request(f"{api_url}/score/text", {"text": text, "domain": args.domain})
            print(json.dumps(result, indent=2))
        else:
            # Local scoring
            print(score_text(text, args.domain).model_dump_json(indent=2))
        return 0

    if args.command == "improve":
        text = Path(args.input).read_text(encoding="utf-8") if args.file else args.input

        if args.api_url:
            api_url = args.api_url.rstrip("/")
            result = _api_request(f"{api_url}/improve", {"text": text, "domain": args.domain})
            print(json.dumps(result, indent=2))
        else:
            from slopguard.detectors.improvement import improve_text
            print(json.dumps(improve_text(text, args.domain), indent=2))
        return 0

    if args.command == "batch":
        raw_items = json.loads(Path(args.path).read_text(encoding="utf-8"))
        items = [TextScoreRequest(**item) for item in raw_items]

        if args.api_url:
            api_url = args.api_url.rstrip("/")
            result = _api_request(f"{api_url}/score/batch", {"items": [{"text": i.text, "domain": i.domain} for i in items]})
            print(json.dumps(result, indent=2))
        else:
            print(score_batch(items).model_dump_json(indent=2))
        return 0

    if args.command == "evaluate":
        path = args.path if args.path else str(_find_samples_path())
        print(json.dumps(evaluate(path), indent=2))
        return 0

    if args.command == "hc3":
        from slopguard.evaluate_hc3 import download_hc3, evaluate_hc3

        samples = download_hc3(domain=args.domain)
        if not samples:
            print("Error: Could not download HC3 dataset.", file=sys.stderr)
            return 1

        results = evaluate_hc3(samples, fast=args.fast)
        print(json.dumps(results, indent=2))

        # Print summary
        overall = results["overall"]
        print(f"\nHC3 Results: F1={overall['f1']:.4f} | Accuracy={overall['accuracy']:.4f} | Samples={results['total_samples']}")
        return 0

    if args.command == "live":
        api_url = args.api_url.rstrip("/")
        try:
            if args.stats:
                data = json.loads(urllib.request.urlopen(
                    urllib.request.Request(f"{api_url}/live/stats",
                    headers={"User-Agent": "slopguard-cli/0.2.0"}), timeout=10
                ).read())
                print(json.dumps(data, indent=2))
            elif args.worst:
                data = json.loads(urllib.request.urlopen(
                    urllib.request.Request(f"{api_url}/live/worst?limit={args.limit}",
                    headers={"User-Agent": "slopguard-cli/0.2.0"}), timeout=10
                ).read())
                print(f"\n{'Score':>6}  {'Oversight':10}  {'Source':16}  Title")
                print("-" * 80)
                for item in data.get("items", []):
                    print(f"{item['score']:>6.1f}  {item['oversight']:10}  {item['source']:16}  {item['title'][:45]}")
            elif args.leaderboard:
                data = json.loads(urllib.request.urlopen(
                    urllib.request.Request(f"{api_url}/live/leaderboard",
                    headers={"User-Agent": "slopguard-cli/0.2.0"}), timeout=10
                ).read())
                print("\nSource Leaderboard (most slop first):")
                for row in data.get("by_source", []):
                    bar = "█" * int(row["slop_pct"] / 5)
                    print(f"  {row['source']:18}  {row['slop_pct']:5.1f}%  {bar}")
                print("\nDomain Breakdown:")
                for row in data.get("by_domain", []):
                    print(f"  {row['domain']:18}  avg={row['avg_score']:4.1f}  slop={row['slop_pct']:4.1f}%")
            else:
                data = json.loads(urllib.request.urlopen(
                    urllib.request.Request(f"{api_url}/live/feed?limit={args.limit}",
                    headers={"User-Agent": "slopguard-cli/0.2.0"}), timeout=10
                ).read())
                print(f"\nLive Feed ({data.get('total_items', 0)} items, ingestion={'active' if data.get('ingestion_active') else 'inactive'})\n")
                print(f"{'Score':>6}  {'Oversight':10}  {'Domain':14}  {'Source':16}  Title")
                print("-" * 90)
                for item in data.get("items", []):
                    print(f"{item['score']:>6.1f}  {item['oversight']:10}  {item['domain']:14}  {item['source']:16}  {item['title'][:35]}")
        except Exception as e:
            print(f"Error: Could not reach API at {api_url}: {e}", file=sys.stderr)
            print(f"Make sure the API is running: uvicorn slopguard.main:app --port 8000", file=sys.stderr)
            return 1
        return 0

    if args.command == "build-dataset":
        import os
        token = args.token or os.environ.get("GITHUB_TOKEN", "")
        try:
            from slopguard.build_full_dataset import build_dataset, evaluate as eval_dataset
            samples = build_dataset(
                token=token,
                output_path=args.output,
                max_per_repo=20,
                include_synthetic=True,
            )
            if args.evaluate and samples:
                print("\nRunning evaluation...")
                results = eval_dataset(samples)
                overall = results["overall"]
                print(f"\nOverall: F1={overall['f1']:.4f}  Precision={overall['precision']:.4f}  Recall={overall['recall']:.4f}")
                for domain, dr in results["per_domain"].items():
                    print(f"  {domain:20s} F1={dr['f1']:.3f} n={dr['n']:3d} gap={dr['score_gap']:+.1f}pts")
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
