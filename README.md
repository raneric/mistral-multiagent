# multiagent

Multi-agent coding crew on the Mistral API: a project-manager agent decomposes a
spec into task files, a developer agent implements each task, and a reviewer
agent drives a fix loop until acceptance criteria pass. Independent tasks run
in parallel; a `run-state.json` lets an interrupted run resume.

Goal: make vibe coding safe — the user describes the app, the agent crew
(PI: PM, developer, reviewer; more roles planned: architect, UI/UX, tester)
builds it with review gates and a workspace sandbox.

## Layout

```
src/multiagent/
├── cli.py               # multiagent run <spec> | multiagent resume
├── config.py            # env-driven Settings, validated once
├── events.py            # JSONL run events (replaces prints)
├── llm/                 # client (retries), runner (agent loop)
├── tools/               # workspace sandbox, registry, filesystem + shell tools
├── agents/              # role specs: pm, developer, reviewer
├── orchestrator/        # task parsing, DAG scheduler, state, run wiring
└── prompts/             # built-in .md templates per role + shared conventions
tests/                   # sandbox, registry, task graph, scheduler, runner
workspace/               # where the agents build (gitignored)
```

## Per-project prompts and conventions

The built-in templates in `src/multiagent/prompts/` are a language-agnostic
baseline. A plan is underway: a discovery phase (agents interviewing the user
in detail) will generate project-specific prompts and conventions into
`<project>/.multiagent/` (e.g. `.multiagent/conventions.md`,
`.multiagent/developer.md`, ...). At build time, any file present in that
folder overrides its built-in counterpart; the built-ins are only used when an
agent builds into this repo's default `workspace/` and no overrides exist.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env       # add your MISTRAL_API_KEY
```

## Usage

```bash
# Full pipeline: decompose spec, implement, review/fix each task
python -m multiagent run specs.md

# Continue after an interruption (uses workspace/run-state.json)
python -m multiagent resume

# Tests and lint
pytest
ruff check src tests
```

## Safety notes

- Agent file tools are sandboxed to `AGENT_WORKSPACE` (symlink and traversal
  escapes are rejected — see `tests/test_sandbox.py`).
- All agents currently get `run_bash`; gate or restrict this before exposing
  to untrusted use.
- Every agent turn is emitted as JSONL events under `workspace/events-*.jsonl`.
