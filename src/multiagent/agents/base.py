"""Agent specs and runner wiring."""
from dataclasses import dataclass

from multiagent.events import EventSink
from multiagent.llm import AgentRunner, get_client
from multiagent.prompts import compose, resolve
from multiagent.tools import default_registry
from multiagent.tools.sandbox import Workspace

ALL_TOOLS = ("read_file", "write_file", "list_files", "run_bash")


@dataclass(frozen=True)
class AgentSpec:
    name: str
    model: str
    system_prompt: str
    allowed_tools: tuple[str, ...] = ALL_TOOLS


def developer_spec(settings) -> AgentSpec:
    return AgentSpec(
        "dev", settings.dev_model,
        compose("developer", "conventions", overrides_dir=settings.prompts_dir),
    )


def reviewer_spec(settings) -> AgentSpec:
    # The reviewer only inspects: it must not edit the workspace.
    return AgentSpec(
        "reviewer", settings.reviewer_model,
        compose("reviewer", "conventions", overrides_dir=settings.prompts_dir),
        allowed_tools=("read_file", "list_files", "run_bash", "write_file"),
    )


def pm_spec(settings) -> AgentSpec:
    return AgentSpec(
        "pm", settings.pm_model,
        compose("pm_decompose", overrides_dir=settings.prompts_dir),
        allowed_tools=("read_file", "list_files", "write_file"),
    )


def discovery_spec(settings) -> AgentSpec:
    """Interviewer agent. Its runner also needs an ask_user tool (see discovery.py)."""
    return AgentSpec(
        "discovery", settings.pm_model,
        resolve("discovery"),
        allowed_tools=("read_file", "write_file", "ask_user"),
    )


def prompt_author_spec(settings) -> AgentSpec:
    """Adapts the five baseline templates into <project>/.multiagent/."""
    return AgentSpec(
        "prompt_author", settings.pm_model,
        resolve("prompt_author"),
        allowed_tools=("read_file", "write_file", "list_files"),
    )


def build_runner(spec: AgentSpec, settings, events: EventSink) -> AgentRunner:
    client = get_client(settings.api_key)
    registry = default_registry(
        Workspace(settings.workspace), bash_timeout=settings.bash_timeout
    )
    runner = AgentRunner(
        client,
        registry.restrict(list(spec.allowed_tools)),
        events,
        system_prompt=spec.system_prompt,
        max_turns=settings.max_agent_turns,
        agent_name=spec.name,
    )
    return runner
