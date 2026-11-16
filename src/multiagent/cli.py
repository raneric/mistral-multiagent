"""Command line entry point.

Usage:
    multiagent run specs.md      # decompose + build
    multiagent resume            # continue an interrupted run
"""
import argparse
import sys

from multiagent.config import Settings
from multiagent.orchestrator.run import resume, run_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="multiagent", description="Multi-agent coding crew on the Mistral API."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="decompose a spec and build it")
    p_run.add_argument("spec", help="path to the spec markdown file")
    sub.add_parser("resume", help="continue an interrupted run from run-state.json")

    args = parser.parse_args(argv)
    try:
        settings = Settings.load()
        if args.command == "run":
            run_spec(args.spec, settings)
        else:
            resume(settings)
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
