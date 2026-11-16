"""The dev -> review -> fix loop for a single task."""
from dataclasses import dataclass

from multiagent.agents.developer import fix_findings, implement_task
from multiagent.agents.reviewer import read_verdict, review_task
from multiagent.events import EventSink
from multiagent.orchestrator.task import Task


@dataclass
class TaskOutcome:
    task_id: str
    passed: bool
    detail: str


def process_task(
    task: Task,
    settings,
    events: EventSink,
    max_fix_cycles: int,
) -> TaskOutcome:
    """Run one task: implement, then review/fix up to max_fix_cycles cycles."""
    report_path = settings.reports_dir / f"review-{task.id}.md"
    events.emit("dispatch", agent="dev", message=f"implement {task.id}")

    dev = implement_task(task, settings, events)
    events.emit("dev_done", agent="dev", message=dev.splitlines()[-1] if dev else "(no output)")

    verdict = ""
    for cycle in range(1, max_fix_cycles + 1):
        events.emit("review", agent="reviewer", message=f"{task.id} (cycle {cycle})")
        review_task(task, report_path, settings, events)
        verdict = read_verdict(report_path)
        events.emit("verdict", agent="reviewer", message=f"{task.id}: {verdict}")
        if verdict.upper().startswith("PASS"):
            return TaskOutcome(task.id, passed=True, detail=verdict)

        if cycle == max_fix_cycles:
            break
        events.emit("dispatch", agent="dev", message=f"fix findings for {task.id}")
        fix_findings(task, report_path, settings, events)

    detail = f"escalation: still failing after {max_fix_cycles} fix cycles; last verdict {verdict}"
    events.emit("escalation", agent="orchestrator", message=f"{task.id}: {detail}")
    return TaskOutcome(task.id, passed=False, detail=detail)
