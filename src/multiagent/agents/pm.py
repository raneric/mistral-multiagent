"""PM agent: decompose a spec into task files, then return the parsed task graph."""
from multiagent.agents.base import build_runner, pm_spec
from multiagent.events import EventSink
from multiagent.orchestrator.task import Task, find_cycle, load_tasks


def decompose(spec_text: str, settings, events: EventSink) -> list[Task]:
    """Run the PM agent, then parse the task files it wrote.

    Note: the PM agent decides the model's plan; we never trust its chat reply,
    only the task files it wrote with write_file.
    """
    runner = build_runner(pm_spec(settings.pm_model), settings, events)
    runner.run(f"Spec:\n\n{spec_text}", settings.pm_model)

    tasks = load_tasks(settings.tasks_dir) if settings.tasks_dir.is_dir() else []
    if not tasks:
        raise RuntimeError(f"PM created no task files in {settings.tasks_dir}")
    if (cycle := find_cycle(tasks)) is not None:
        raise RuntimeError(f"PM produced a dependency cycle: {' -> '.join(cycle)}")
    return tasks
