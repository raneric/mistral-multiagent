from pathlib import Path

import pytest

from multiagent.orchestrator.task import (
    find_cycle,
    load_task,
    parse_dependencies,
    wave_order,
)


def write_task(tmp_path: Path, name: str, deps: str) -> Path:
    p = tmp_path / name
    p.write_text(f"# {name}\nDepends on: {deps}\n", encoding="utf-8")
    return p


def test_parse_dependencies_variants() -> None:
    assert parse_dependencies("Depends on: task-001, task-002") == ["task-001", "task-002"]
    assert parse_dependencies("Depends on: none") == []
    assert parse_dependencies("Depends on: -") == []
    assert parse_dependencies("nothing here") == []
    assert parse_dependencies("depends on: task-003.md") == ["task-003"]


def test_load_task_reads_id_and_deps(tmp_path: Path) -> None:
    path = write_task(tmp_path, "task-002.md", "task-001")
    task = load_task(path)
    assert task.id == "task-002"
    assert task.deps == ["task-001"]


def test_find_cycle_detects_loop(tmp_path: Path) -> None:
    write_task(tmp_path, "task-001.md", "task-003")
    write_task(tmp_path, "task-002.md", "task-001")
    write_task(tmp_path, "task-003.md", "task-002")
    tasks = [load_task(p) for p in sorted(tmp_path.glob("*.md"))]
    cycle = find_cycle(tasks)
    assert cycle is not None
    assert "task-001" in cycle


def test_find_cycle_linear_ok(tmp_path: Path) -> None:
    write_task(tmp_path, "task-001.md", "none")
    write_task(tmp_path, "task-002.md", "task-001")
    tasks = [load_task(p) for p in sorted(tmp_path.glob("*.md"))]
    assert find_cycle(tasks) is None


def test_wave_order_groups_independent_tasks(tmp_path: Path) -> None:
    write_task(tmp_path, "task-001.md", "none")
    write_task(tmp_path, "task-002.md", "task-001")
    write_task(tmp_path, "task-003.md", "task-001")
    tasks = [load_task(p) for p in sorted(tmp_path.glob("*.md"))]
    waves = wave_order(tasks)
    assert [len(w) for w in waves] == [1, 2]


def test_wave_order_unknown_dep_raises(tmp_path: Path) -> None:
    write_task(tmp_path, "task-001.md", "task-999")
    tasks = [load_task(p) for p in sorted(tmp_path.glob("*.md"))]
    with pytest.raises(ValueError, match="task-999"):
        wave_order(tasks)
