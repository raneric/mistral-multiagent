"""Reviewer agent: produce a structured review report, and parse verdicts back."""
from pathlib import Path

from multiagent.agents.base import build_runner, reviewer_spec
from multiagent.events import EventSink
from multiagent.orchestrator.task import Task


def review_task(task: Task, report_path: Path, settings, events: EventSink) -> str:
    runner = build_runner(reviewer_spec(settings), settings, events)
    user_task = (
        f"Review the implementation of {task.path}. "
        f"Write your report to {report_path}."
    )
    result = runner.run(user_task, settings.reviewer_model)
    return result.final_text


def read_verdict(report_path: Path) -> str:
    try:
        report = Path(report_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return "FIX_REQUIRED"  # fail safe: missing report means another cycle
    for line in report.splitlines():
        if line.strip().startswith("## Verdict:"):
            return line.split("Verdict:")[1].strip()
    return "FIX_REQUIRED"  # fail safe: unparseable report means another cycle
