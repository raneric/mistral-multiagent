"""Discovery phase: interview the user, write spec.md, generate project prompts.

Two agents run in sequence:
1. interviewer: asks the user questions through the interactive ask_user tool
   and writes <workspace>/spec.md (the spec on behalf of the user).
2. prompt author: adapts the five baseline prompt templates into
   <workspace>/.multiagent/ using the spec + transcript. A code-level
   validator checks the machine-parsed contracts and forces one regeneration
   if they are violated.

Afterwards `multiagent run` picks up spec.md and the generated overrides
automatically.
"""
import threading
from pathlib import Path

from multiagent.agents.base import build_runner, discovery_spec, prompt_author_spec
from multiagent.events import EventSink
from multiagent.llm import AgentRunner, get_client
from multiagent.prompts import load
from multiagent.tools import default_registry
from multiagent.tools.sandbox import Workspace

GENERATED_PROMPTS = ("conventions.md", "developer.md", "reviewer.md", "pm_decompose.md", "pm_fix.md")

# Markers that generated prompts MUST contain for the pipeline to work:
# verdict parsing, runtime placeholders, and task-file naming are code contracts.
_REQUIRED_MARKERS = {
    "reviewer.md": ["## Verdict:", "FIX_REQUIRED"],
    "pm_fix.md": ["{task_path}", "{report_path}"],
    "pm_decompose.md": ["tasks/task-"],
    "conventions.md": [],
    "developer.md": [],
}
_MAX_AUTHOR_ATTEMPTS = 2


class InterviewSession:
    """Collects interviewer questions and user answers; renders the transcript."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def ask_user(self, question: str) -> str:
        """Ask the user one question in the terminal and return their answer."""
        print(f"\n[discovery] {question.strip()}\n> ", end="", flush=True)
        try:
            answer = input()
        except EOFError:
            return "(input stream closed - conclude the interview with what you have)"
        with self._lock:
            self.entries.append((question.strip(), answer.strip()))
        return answer

    def record(self, question: str, answer: str) -> None:
        with self._lock:
            self.entries.append((question.strip(), answer.strip()))

    def render(self) -> str:
        lines = ["# Discovery transcript", ""]
        for index, (question, answer) in enumerate(self.entries, start=1):
            lines += [f"## Q{index}. {question}", "", answer or "(no answer)", ""]
        return "\n".join(lines)


def validate_prompts(overrides_dir: Path) -> list[str]:
    """Check the generated prompts against code-level contracts. Empty list = valid."""
    overrides_dir = Path(overrides_dir)
    if not overrides_dir.is_dir():
        return [f"{overrides_dir} does not exist - nothing was generated"]
    violations: list[str] = []
    for filename, markers in _REQUIRED_MARKERS.items():
        path = overrides_dir / filename
        if not path.is_file():
            violations.append(f"{filename}: file not generated")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                violations.append(f"{filename}: missing required marker {marker!r}")
    return violations


def _interviewer_runner(settings, events: EventSink, session: InterviewSession) -> AgentRunner:
    registry = default_registry(Workspace(settings.workspace), bash_timeout=settings.bash_timeout)
    registry.add(session.ask_user)
    spec = discovery_spec(settings)
    return AgentRunner(
        get_client(settings.api_key),
        registry.restrict(list(spec.allowed_tools)),
        events,
        system_prompt=spec.system_prompt,
        max_turns=settings.max_agent_turns,
        agent_name=spec.name,
    )


def _compose_author_task(spec_path: Path, transcript: str, violations: list[str]) -> str:
    baselines = "\n\n".join(
        f'<baseline name="{name}">\n{load(name)}\n</baseline>'
        for name in ("conventions", "developer", "reviewer", "pm_decompose", "pm_fix")
    )
    parts = [
        "Generate the five project prompt files in .multiagent/ now.\n",
        f"## Project spec (spec.md)\n\n{spec_path.read_text(encoding='utf-8')}",
        f"## Discovery transcript\n\n{transcript}",
    ]
    if violations:
        parts.append(
            "## Violations from your previous generation (fix ALL of them)\n- "
            + "\n- ".join(violations)
        )
    parts.append(f"## Built-in baseline templates\n\n{baselines}")
    return "\n\n".join(parts)


def run_discovery(
    idea: str,
    settings,
    events: EventSink | None = None,
    interviewer: AgentRunner | None = None,
    author: AgentRunner | None = None,
) -> None:
    """Full discovery: interview -> spec.md -> .multiagent/ prompt overrides."""
    events = events or EventSink(echo=True)
    events.emit("discovery_start", agent="discovery", message=f"idea: {idea[:80]}" if idea else "no initial idea")

    session = InterviewSession()
    interviewer = interviewer or _interviewer_runner(settings, events, session)
    user_task = (
        f"The user's initial idea: {idea}\n\nStart the interview now."
        if idea.strip()
        else "No initial idea was given. Start with a broad question about what the user wants to build."
    )
    interviewer.run(user_task, settings.pm_model)

    spec_path = settings.workspace / "spec.md"
    if not spec_path.is_file():
        raise RuntimeError(
            "the interview ended without writing spec.md - re-run 'multiagent discover'"
        )

    author = author or build_runner(prompt_author_spec(settings), settings, events)
    violations: list[str] = []
    for attempt in range(1, _MAX_AUTHOR_ATTEMPTS + 1):
        author.run(
            _compose_author_task(spec_path, session.render(), violations),
            settings.pm_model,
        )
        violations = validate_prompts(settings.prompts_dir)
        if not violations:
            events.emit(
                "discovery_done",
                agent="discovery",
                message=f"spec.md + {len(GENERATED_PROMPTS)} project prompts ready",
            )
            return
        events.emit("prompt_invalid", agent="discovery", message="; ".join(violations[:5]))

    raise RuntimeError(
        "generated prompts violate machine contracts after "
        f"{_MAX_AUTHOR_ATTEMPTS} attempts: " + "; ".join(violations)
    )
