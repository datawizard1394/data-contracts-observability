"""Command-line interface for the synthetic observability toolkit."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .contract import ContractError, load_contract
from .engine import evaluate
from .io import read_json, write_json
from .lineage import LineageError, lineage_context, load_lineage
from .models import CheckStatus, ValidationReport
from .reporting import console_summary, incident_summary, render_markdown


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid ISO-8601 timestamp: {value}") from exc
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="data-observer",
        description="Validate a CSV against an executable data contract.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="evaluate a contract and write artifacts")
    run.add_argument("--contract", required=True, type=Path)
    run.add_argument("--data", required=True, type=Path)
    run.add_argument("--lineage", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("build/observability"))
    run.add_argument("--now", type=_timestamp)
    run.add_argument(
        "--fail-on",
        choices=("failure", "never"),
        default="failure",
        help="return a non-zero status for failed checks (default: failure)",
    )

    lineage = subcommands.add_parser("lineage", help="inspect one lineage asset")
    lineage.add_argument("--manifest", required=True, type=Path)
    lineage.add_argument("--asset", required=True)

    summary = subcommands.add_parser("summarize", help="render an existing JSON report")
    summary.add_argument("--report", required=True, type=Path)
    summary.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    return parser


def _run(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    context = None
    if args.lineage:
        context = lineage_context(load_lineage(args.lineage), contract.dataset)
    report = evaluate(
        contract,
        args.data,
        now=args.now,
        lineage=context,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "report.json", report.to_dict())
    write_json(args.output_dir / "incident.json", incident_summary(report))
    (args.output_dir / "incident-summary.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    if context is not None:
        write_json(args.output_dir / "lineage-context.json", context)
    print(console_summary(report))
    print(f"Artifacts: {args.output_dir}")
    has_failures = report.counts[CheckStatus.FAIL.value] > 0
    return 1 if has_failures and args.fail_on == "failure" else 0


def _lineage(args: argparse.Namespace) -> int:
    context = lineage_context(load_lineage(args.manifest), args.asset)
    print(json.dumps(context, indent=2, sort_keys=True))
    return 0


def _summarize(args: argparse.Namespace) -> int:
    report = ValidationReport.from_dict(read_json(args.report))
    if args.format == "markdown":
        print(render_markdown(report), end="")
    elif args.format == "json":
        print(json.dumps(incident_summary(report), indent=2, sort_keys=True))
    else:
        print(console_summary(report))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "lineage":
            return _lineage(args)
        return _summarize(args)
    except (ContractError, LineageError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
