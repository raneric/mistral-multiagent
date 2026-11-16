"""Durable run state: task statuses survive crashes and can be resumed."""
import json
from pathlib import Path

STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_BLOCKED = "BLOCKED"
STATUS_SKIPPED = "SKIPPED"


class RunState:
    def __init__(self, path: Path):
        self.path = path
        self.statuses: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.statuses = data.get("statuses", {})
            self.errors = data.get("errors", {})

    def set(self, task_id: str, status: str, error: str = "") -> None:
        self.statuses[task_id] = status
        if error:
            self.errors[task_id] = error
        else:
            self.errors.pop(task_id, None)
        self.save()

    def get(self, task_id: str) -> str | None:
        return self.statuses.get(task_id)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"statuses": self.statuses, "errors": self.errors}, indent=2),
            encoding="utf-8",
        )
