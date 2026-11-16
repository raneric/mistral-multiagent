"""Command line entry point.

Usage:
    multiagent discover "app idea"   # interview + spec.md + project prompts
    multiagent run [spec]            # decompose + build (default: <workspace>/spec.md)
    multiagent resume                # continue an interrupted run
"""
import argparse
import sys
from pathlib import Path

from multiagent.config import Settings
from multiagent.discovery import run_discovery
from multiagent.orchestrator.run import resume, run_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="multiagent", description="Multi-agent coding crew on the Mistral API."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_discover = sub.add_parser(
        "discover", help="interview the user, write spec.md and project prompts"
    )
    p_discover.add_argument(
        "idea", nargs="*", help="initial app idea (optional; the agent will ask)"
    )
    p_discover.add_argument(
        "--run", action="store_true", help="start building immediately after discovery"
    )

    p_run = sub.add_parser("run", help="decompose a spec and build it")
    p_run.add_argument(
        "spec", nargs="?", help="path to the spec markdown file (default: <workspace>/spec.md)"
    )
    sub.add_parser("resume", help="continue an interrupted run from run-state.json")

    args = parser.parse_args(argv)
    try:
        settings = Settings.load()
        if args.command == "discover":
            if not sys.stdin.isatty():
                print("error: discovery needs an interactive terminal", file=sys.stderr)
                return 1
            run_discovery(" ".join(args.idea).strip(), settings)
            if args.run:
                run_spec(settings.workspace / "spec.md", settings)
        elif args.command == "run":
            spec = args.spec or settings.workspace / "spec.md"
            if not Path(spec).is_file():
                raise FileNotFoundError(
                    f"no spec at {spec}; run 'multiagent discover' first or pass a spec file"
                )
            run_spec(spec, settings)
        else:
            resume(settings)
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
