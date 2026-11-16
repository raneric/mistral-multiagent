from types import SimpleNamespace

import pytest

import multiagent.orchestrator.scheduler as scheduler_mod
from multiagent.events import EventSink
from multiagent.orchestrator.scheduler import Scheduler
from multiagent.orchestrator.state import RunState
from multiagent.orchestrator.task import Task


@pytest.fixture()
def settings(tmp_path):
    return SimpleNamespace(max_fix_cycles=2, workspace=tmp_path)


@pytest.fixture()
def events() -> EventSink:
    return EventSink(None, echo=False)


def make_tasks(tmp_path, deps: dict[str, list[str]]):
    tasks = []
    for i, (tid, task_deps) in enumerate(deps.items(), start=1):
        tasks.append(Task(id=tid, path=tmp_path / f"task-{i:03d}.md", deps=task_deps))
    return tasks


def run_scheduler(monkeypatch, tasks, settings, events, results):
    def fake_process(task, settings, events, max_fix_cycles):
        outcome = results[task.id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(scheduler_mod, "process_task", fake_process)
    state = RunState(settings.workspace / "run-state.json")
    return Scheduler(tasks, settings, events, state, max_workers=2).run()


def test_independent_tasks_run_then_pass(tmp_path, settings, events, monkeypatch):
    tasks = make_tasks(tmp_path, {"task-001": [], "task-002": []})
    results = {t.id: SimpleNamespace(task_id=t.id, passed=True, detail="PASS") for t in tasks}
    summary = run_scheduler(monkeypatch, tasks, settings, events, results)
    assert summary.done == ["task-001", "task-002"]
    assert not summary.failed and not summary.blocked


def test_failure_blocks_dependents(tmp_path, settings, events, monkeypatch):
    tasks = make_tasks(
        tmp_path, {"task-001": [], "task-002": ["task-001"], "task-003": []}
    )
    results = {
        "task-001": SimpleNamespace(task_id="task-001", passed=False, detail="bad"),
        "task-003": SimpleNamespace(task_id="task-003", passed=True, detail="PASS"),
    }
    summary = run_scheduler(monkeypatch, tasks, settings, events, results)
    assert summary.failed == ["task-001"]
    assert summary.blocked == ["task-002"]
    assert summary.done == ["task-003"]
    assert summary.errors["task-001"]


def test_crashed_task_is_recorded_and_run_survives(tmp_path, settings, events, monkeypatch):
    tasks = make_tasks(tmp_path, {"task-001": [], "task-002": []})
    results = {
        "task-001": RuntimeError("model exploded"),
        "task-002": SimpleNamespace(task_id="task-002", passed=True, detail="PASS"),
    }
    summary = run_scheduler(monkeypatch, tasks, settings, events, results)
    assert summary.failed == ["task-001"]
    assert summary.done == ["task-002"]
    assert "RuntimeError" in summary.errors["task-001"]


def test_resume_skips_tasks_already_done(tmp_path, settings, events, monkeypatch):
    tasks = make_tasks(tmp_path, {"task-001": [], "task-002": ["task-001"]})
    state = RunState(settings.workspace / "run-state.json")
    state.set("task-001", "DONE")
    state.save()

    called: list[str] = []

    def fake_process(task, *args):
        called.append(task.id)
        return SimpleNamespace(task_id=task.id, passed=True, detail="PASS")

    monkeypatch.setattr(scheduler_mod, "process_task", fake_process)
    Scheduler(tasks, settings, events, state, max_workers=2).run()
    assert called == ["task-002"]
