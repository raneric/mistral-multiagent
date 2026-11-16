# Spec: CLI task manager

Build a Python CLI tool in workspace/src that stores tasks in workspace/data/tasks.json.

## Task 1: Core storage
Depends on: none
- `add <title>` appends a task with an id and saves to data/tasks.json
- `list` prints all tasks
- Acceptance: pytest tests/test_storage.py passes (provide the tests)

## Task 2: Completion command
Depends on: task-001
- `done <id>` marks a task completed
- Acceptance: pytest tests/test_done.py passes
