from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import CodeReviewAgent
from .config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review a source-code project with an Agent.")
    parser.add_argument("project", nargs="?", default=".", help="Project directory to review")
    parser.add_argument("--dry-run", action="store_true", help="Run deterministic checks without an LLM")
    parser.add_argument("--output", type=Path, help="Write the JSON report to this file")
    parser.add_argument("--model", help="Override CODE_REVIEW_MODEL")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env(Path(".env"))
    if args.model:
        settings = Settings(
            api_key=settings.api_key,
            base_url=settings.base_url,
            model=args.model,
            max_files=settings.max_files,
            max_chars=settings.max_chars,
            demo_access_password=settings.demo_access_password,
            max_reviews_per_session=settings.max_reviews_per_session,
        )
    report = CodeReviewAgent(settings).review(args.project, dry_run=args.dry_run)
    rendered = json.dumps(report.model_dump(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Report written to {args.output.resolve()}")
    else:
        print(rendered)
