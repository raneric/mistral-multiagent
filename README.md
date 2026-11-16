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
baseline. The discovery phase generates project-specific replacements.
At build time, any file present in that folder overrides its built-in
counterpart; the built-ins are only used when an agent builds into this repo's
default `workspace/` and no overrides exist.

## Discovery flow

```bash
python -m multiagent discover "I want a habit tracker for my phone"
#   -> an interviewer agent asks you focused questions in the terminal
#   (one question per prompt, 5-10 total)
#   -> it writes <workspace>/spec.md on your behalf
#   -> a prompt-author agent adapts the five templates for your chosen stack
#      into <workspace>/.multiagent/{conventions,developer,reviewer,
#      pm_decompose,pm_fix}.md
#   -> code-level checks verify the machine contracts (verdict marker,
#      {task_path}/{report_path} placeholders, task-NNN naming) and force a
#      regeneration if the author broke them

python -m multiagent run        # builds from <workspace>/spec.md (+ overrides)
```

`run` still accepts an explicit spec file (`python -m multiagent run
specs.md`) when you write your own; in that case discovery is skipped and the
built-in (or any pre-existing) `.multiagent/` overrides apply.

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
- The build agents get `run_bash`; the interviewer gets an interactive
  `ask_user` tool, and its prompt allows writing only `spec.md` (instruction-
  level restriction, not yet sandbox-enforced). Gate or restrict `run_bash`
  before exposing to untrusted use.
- Every agent turn is emitted as JSONL events under `workspace/events-*.jsonl`.
