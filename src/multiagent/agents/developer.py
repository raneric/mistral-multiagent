"""Developer agent: implement a task, or fix review findings."""
from multiagent.agents.base import build_runner, developer_spec
from multiagent.events import EventSink
from multiagent.orchestrator.task import Task
from multiagent.prompts import resolve


def implement_task(task: Task, settings, events: EventSink) -> str:
    runner = build_runner(developer_spec(settings), settings, events)
    result = runner.run(f"Implement the task described in {task.path}.", settings.dev_model)
    return result.final_text


def fix_findings(task: Task, report_path, settings, events: EventSink) -> str:
    runner = build_runner(developer_spec(settings), settings, events)
    user_task = resolve("pm_fix", settings.prompts_dir).format(
        task_path=task.path, report_path=report_path
    )
    result = runner.run(user_task, settings.dev_model)
    return result.final_text
