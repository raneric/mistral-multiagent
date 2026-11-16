"""High-level wiring: full run and resume."""
from datetime import datetime, timezone
from pathlib import Path

from multiagent.agents.pm import decompose
from multiagent.events import EventSink
from multiagent.orchestrator.scheduler import Scheduler
from multiagent.orchestrator.state import RunState
from multiagent.orchestrator.task import load_tasks


def _read_spec(spec_path: str | Path) -> str:
    path = Path(spec_path)
    if not path.is_file():
        raise FileNotFoundError(f"spec file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"spec file is empty: {path}")
    return text


def _scheduler(settings, events: EventSink) -> Scheduler:
    if not settings.tasks_dir.is_dir():
        raise RuntimeError(
            f"no task directory at {settings.tasks_dir}; run 'multiagent run <spec>' first"
        )
    tasks = load_tasks(settings.tasks_dir)
    if not tasks:
        raise RuntimeError(
            f"no task files in {settings.tasks_dir}; run 'multiagent run <spec>' first"
        )
    state = RunState(settings.workspace / "run-state.json")
    return Scheduler(tasks, settings, events, state, max_workers=settings.max_workers)


def run_spec(spec_path: str | Path, settings) -> None:
    """Full pipeline: PM decomposes the spec, then the scheduler runs the DAG."""
    events = EventSink(_events_path(settings))
    settings.tasks_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)

    spec = _read_spec(spec_path)

    tasks = decompose(spec, settings, events)
    print(f"[pm] created {len(tasks)} tasks")
    # A fresh decomposition invalidates any previous state for these task ids.
    state = RunState(settings.workspace / "run-state.json")
    state.statuses, state.errors = {}, {}
    state.save()
    scheduler = Scheduler(tasks, settings, events, state, max_workers=settings.max_workers)
    summary = scheduler.run()
    print(f"[pm] done. {len(summary.done)} task(s) passed review "
          f"({len(summary.failed)} failed, {len(summary.blocked)} blocked).")


def resume(settings) -> None:
    """Resume an interrupted run using run-state.json; no re-decomposition."""
    events = EventSink(_events_path(settings, tag="resume"))
    scheduler = _scheduler(settings, events)
    summary = scheduler.run()
    print(f"[pm] resumed. {summary.as_text()}")


def _events_path(settings, tag: str = "run") -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return settings.workspace / f"events-{tag}-{stamp}.jsonl"
