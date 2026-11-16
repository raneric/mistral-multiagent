"""Task files: parse ids, dependencies, and validate the task graph."""
import re
from dataclasses import dataclass, field
from pathlib import Path

TASK_FILE_RE = re.compile(r"task-\d+\.md")
DEPS_RE = re.compile(r"Depends on:\s*(.+)", re.IGNORECASE)


@dataclass
class Task:
    id: str
    path: Path
    deps: list[str] = field(default_factory=list)


def parse_dependencies(text: str) -> list[str]:
    m = DEPS_RE.search(text)
    if not m or m.group(1).strip().lower() in ("none", "-"):
        return []
    return [dep.strip().removesuffix(".md") for dep in m.group(1).split(",") if dep.strip()]


def load_task(path: Path) -> Task:
    task_id = TASK_FILE_RE.fullmatch(path.name).group(0).removesuffix(".md")
    deps = parse_dependencies(path.read_text(encoding="utf-8"))
    return Task(id=task_id, path=path, deps=deps)


def load_tasks(tasks_dir: Path) -> list[Task]:
    return [load_task(p) for p in sorted(tasks_dir.iterdir()) if TASK_FILE_RE.fullmatch(p.name)]


def find_cycle(tasks: list[Task]) -> list[str] | None:
    """Return one dependency cycle as a list of task ids, or None."""
    ids = {t.id for t in tasks}
    graph = {t.id: [d for d in t.deps if d in ids] for t in tasks}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for dep in graph[node]:
            if color[dep] == GRAY:
                return stack[stack.index(dep):] + [dep]
            if color[dep] == WHITE and (c := visit(dep)):
                return c
        stack.pop()
        color[node] = BLACK
        return None

    for node in graph:
        if color[node] == WHITE and (cycle := visit(node)):
            return cycle
    return None


def wave_order(tasks: list[Task]) -> list[list[Task]]:
    """Group tasks into dependency waves; raises ValueError on cycles."""
    if (cycle := find_cycle(tasks)) is not None:
        raise ValueError(f"dependency cycle detected: {' -> '.join(cycle)}")
    by_id = {t.id: t for t in tasks}
    remaining = [t.id for t in tasks]
    done: set[str] = set()
    waves: list[list[Task]] = []
    while remaining:
        wave = [t for t in (by_id[i] for i in remaining) if all(d in done for d in t.deps)]
        if not wave:
            missing = sorted(
                {
                    dep
                    for i in remaining
                    for dep in by_id[i].deps
                    if dep not in done and dep not in remaining
                }
            )
            raise ValueError(f"unresolvable dependencies (missing or failed): {missing}")
        waves.append(wave)
        for t in wave:
            done.add(t.id)
        remaining = [i for i in remaining if i not in done]
    return waves
