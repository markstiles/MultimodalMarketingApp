#!/usr/bin/env python
"""CLI entry point for headless conversation simulation.

Runs the AI marketing pipeline without the browser UI, using a second LLM
to simulate a marketing professional driving the conversation.

Usage — free-form scenario:
    python -m scripts.headless_run "Create a campaign brief for product X" \\
        --max-turns 15 --files /path/to/assets --output results.json --verbose

Usage — named scenario from the simulation test registry:
    python -m scripts.headless_run --scenario research-full --verbose
    python -m scripts.headless_run --list-scenarios

Environment variables required:
    LLM_API_KEY          OpenAI-compatible API key
    DATABASE_URL         PostgreSQL connection string
    HEADLESS_SITE_ID     Sitecore site ID (falls back to LOCAL_SITE_ID)
    HEADLESS_PAGE_ID     Sitecore page ID (falls back to LOCAL_PAGE_ID)

Optional:
    HEADLESS_LANGUAGE      Language code, default "en"
    HEADLESS_USER_ID       User ID for session tracking, default "headless-runner"
    HEADLESS_USER_NAME     Display name
    HEADLESS_USER_EMAIL    Email address
    HEADLESS_DRIVER_MODEL  Override model for the driver LLM
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure the backend package is on the path when run as a script
_here = Path(__file__).resolve().parent.parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Headless conversation simulation for the AI marketing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source_group = p.add_mutually_exclusive_group()
    source_group.add_argument(
        "scenario_text",
        nargs="?",
        metavar="SCENARIO",
        help="Free-form scenario description (the goal the simulated user is trying to achieve)",
    )
    source_group.add_argument(
        "--scenario",
        metavar="ID",
        help="Run a named scenario from the simulation test registry (see --list-scenarios)",
    )
    source_group.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List all available named scenarios and exit",
    )

    p.add_argument(
        "--max-turns",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of conversation turns (default: 20, or scenario default)",
    )
    p.add_argument(
        "--files",
        default=None,
        metavar="SOURCE",
        help=(
            "File source: a directory path, or comma-separated name=/path pairs. "
            "Files are available to the driver LLM via [ATTACH: name] markers."
        ),
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help="Write the run result as JSON to this file (default: stdout)",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each turn to stdout as the run progresses",
    )
    p.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level (default: WARNING)",
    )
    return p


def _list_scenarios() -> None:
    from tests.simulation.scenarios import SCENARIOS

    def _safe(text: str, width: int = 80) -> str:
        return text[:width].encode("ascii", errors="replace").decode("ascii")

    print("Available simulation scenarios:\n")
    for sid, sc in sorted(SCENARIOS.items()):
        print(f"  {sid:<28}  {_safe(sc.name)}")
        print(f"  {'':<28}  {_safe(sc.description)}")
        print()
    print("Run with: python -m scripts.headless_run --scenario <id> --verbose")


def _serialize_result(result) -> dict:
    return {
        "scenario": result.scenario,
        "completed": result.completed,
        "total_turns": result.total_turns,
        "context": {
            "site_id": result.context.site_id,
            "page_id": result.context.page_id,
            "language": result.context.language,
            "user_id": result.context.user_id,
        },
        "turns": [
            {
                "turn": r.turn,
                "user_message": r.user_message,
                "assistant_response": r.assistant_response,
                "tool_calls": r.tool_calls,
                "canvas_reload": r.canvas_reload,
                "attached_files": r.attached_files,
            }
            for r in result.turns
        ],
    }


async def _run(args: argparse.Namespace) -> int:
    from app.headless.runner import HeadlessRunner

    if args.scenario:
        from tests.simulation.scenarios import get_scenario
        sc = get_scenario(args.scenario)
        scenario_text = sc.scenario_prompt
        max_turns = args.max_turns or sc.max_turns
        files_source = args.files or sc.files_source
    elif args.scenario_text:
        scenario_text = args.scenario_text
        max_turns = args.max_turns or 20
        files_source = args.files
    else:
        print("error: provide a SCENARIO argument or --scenario ID", file=sys.stderr)
        return 2

    runner = HeadlessRunner(
        scenario=scenario_text,
        max_turns=max_turns,
        files_source=files_source,
        verbose=args.verbose,
    )

    result = await runner.run()

    payload = _serialize_result(result)

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if args.verbose:
            print(f"\n[headless] Result written to {args.output}")
    else:
        print(json.dumps(payload, indent=2))

    if args.verbose:
        print(f"\n[headless] {result.summary()}")

    return 0 if result.completed else 1


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_scenarios:
        _list_scenarios()
        return

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
