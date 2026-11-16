"""Wave scheduler over the task DAG, with persistence and failure isolation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from multiagent.events import EventSink
from multiagent.orchestrator.pipeline import TaskOutcome, process_task
from multiagent.orchestrator.state import (
    STATUS_BLOCKED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_SKIPPED,
    RunState,
)
from multiagent.orchestrator.task import Task, find_cycle


@dataclass
class RunSummary:
    done: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def as_text(self) -> str:
        return (
            f"done={len(self.done)} failed={len(self.failed)} blocked={len(self.blocked)}\n"
            f"failed tasks: {', '.join(self.failed) or '-'}\n"
            f"blocked tasks: {', '.join(self.blocked) or '-'}"
        )


class Scheduler:
    def __init__(
        self,
        tasks: list[Task],
        settings,
        events: EventSink,
        state: RunState,
        max_workers: int = 3,
    ):
        self.tasks = {t.id: t for t in tasks}
        self.settings = settings
        self.events = events
        self.state = state
        self.max_workers = max_workers

    def _terminal_failures(self) -> set[str]:
        return {
            tid for tid, status in self.state.statuses.items()
            if status in (STATUS_BLOCKED, STATUS_SKIPPED)
        }

    def run(self) -> RunSummary:
        if (cycle := find_cycle(list(self.tasks.values()))) is not None:
            raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")

        # Resume: tasks already DONE are never rescheduled.
        pending = {
            tid for tid in self.tasks if self.state.get(tid) != STATUS_DONE
        }
        terminal = self._terminal_failures()
        while pending:
            # Tasks depending on permanently stuck work are BLOCKED, removed.
            for tid in [t for t in pending if self.tasks[t].deps and any(
                d in terminal for d in self.tasks[t].deps
            )]:
                self.state.set(tid, STATUS_BLOCKED)
                pending.remove(tid)
            terminal = self._terminal_failures()

            ready = [
                self.tasks[tid] for tid in pending
                if all(self.state.get(dep) == STATUS_DONE
                       for dep in self.tasks[tid].deps)
            ]
            if not ready:
                # Anything left is unschedulable (missing deps or a stuck graph).
                for tid in sorted(pending):
                    self.state.set(tid, STATUS_BLOCKED)
                pending.clear()
                break

            self.events.emit(
                "wave", agent="orchestrator", message=f"starting {[t.id for t in ready]}"
            )
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = {
                    pool.submit(process_task, t, self.settings, self.events,
                                self.settings.max_fix_cycles): t
                    for t in ready
                }
                for future, task in futures.items():
                    try:
                        outcome: TaskOutcome = future.result()
                        fate = STATUS_DONE if outcome.passed else STATUS_FAILED
                        self.state.set(task.id, fate, "" if outcome.passed else outcome.detail)
                    except Exception as e:  # one broken task must not kill the run
                        self.state.set(task.id, STATUS_FAILED, f"{type(e).__name__}: {e}")
                    pending.discard(task.id)

        summary = RunSummary()
        for tid in sorted(self.tasks):
            status = self.state.get(tid)
            if status == STATUS_DONE:
                summary.done.append(tid)
            elif status == STATUS_FAILED:
                summary.failed.append(tid)
                if tid in self.state.errors:
                    summary.errors[tid] = self.state.errors[tid]
            elif status in (STATUS_BLOCKED, STATUS_SKIPPED):
                summary.blocked.append(tid)
            else:  # never reached (defensive with fresh state)
                self.state.set(tid, STATUS_BLOCKED)
                summary.blocked.append(tid)
        self.events.emit("run_done", agent="orchestrator", message=summary.as_text())
        return summary
