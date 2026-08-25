from __future__ import annotations

import argparse
import json
from pathlib import Path

from codereview_agent.agent import CodeReviewAgent
from codereview_agent.config import Settings


def _load_case(case_dir: Path) -> dict[str, object]:
    return json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))


def run_suite(cases_dir: Path, mode: str) -> dict[str, object]:
    settings = Settings.from_env(Path(".env"))
    agent = CodeReviewAgent(settings)
    case_results: list[dict[str, object]] = []
    total_tp = total_fp = total_fn = 0

    for case_dir in sorted(path for path in cases_dir.iterdir() if path.is_dir()):
        expected_data = _load_case(case_dir)
        expected = {
            (str(item["title"]), str(item["file"]))
            for item in expected_data.get("findings", [])
        }
        report = agent.review(case_dir, dry_run=mode == "offline")
        actual = {(issue.title, issue.file) for issue in report.issues}
        true_positive = expected & actual
        false_positive = actual - expected
        false_negative = expected - actual
        total_tp += len(true_positive)
        total_fp += len(false_positive)
        total_fn += len(false_negative)
        case_results.append(
            {
                "case": case_dir.name,
                "passed": not false_positive and not false_negative,
                "expected": sorted(expected),
                "actual": sorted(actual),
                "false_positive": sorted(false_positive),
                "false_negative": sorted(false_negative),
            }
        )

    precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 1.0
    recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 1.0
    passed_cases = sum(1 for item in case_results if item["passed"])
    return {
        "mode": mode,
        "cases": len(case_results),
        "passed_cases": passed_cases,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "results": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CodeReviewAgent evaluation cases.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).parent / "cases",
        help="Directory containing one subdirectory per evaluation case",
    )
    parser.add_argument("--mode", choices=("offline", "llm"), default="offline")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    result = run_suite(args.cases, args.mode)
    print(
        f"mode={result['mode']} cases={result['cases']} "
        f"passed={result['passed_cases']} precision={result['precision']:.2f} "
        f"recall={result['recall']:.2f}"
    )
    for case in result["results"]:
        status = "PASS" if case["passed"] else "FAIL"
        print(f"{status}: {case['case']}")
        if case["false_positive"] or case["false_negative"]:
            print(f"  false_positive={case['false_positive']}")
            print(f"  false_negative={case['false_negative']}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
