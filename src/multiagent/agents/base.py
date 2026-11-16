"""Agent specs and runner wiring."""
from dataclasses import dataclass

from multiagent.events import EventSink
from multiagent.llm import AgentRunner, get_client
from multiagent.prompts import load
from multiagent.tools import default_registry
from multiagent.tools.sandbox import Workspace

ALL_TOOLS = ("read_file", "write_file", "list_files", "run_bash")


@dataclass(frozen=True)
class AgentSpec:
    name: str
    model: str
    system_prompt: str
    allowed_tools: tuple[str, ...] = ALL_TOOLS


def developer_spec(model: str) -> AgentSpec:
    return AgentSpec("dev", model, load("developer"))


def reviewer_spec(model: str) -> AgentSpec:
    # The reviewer only inspects: it must not edit the workspace.
    return AgentSpec(
        "reviewer", model, load("reviewer"),
        allowed_tools=("read_file", "list_files", "run_bash", "write_file"),
    )


def pm_spec(model: str) -> AgentSpec:
    return AgentSpec("pm", model, load("pm_decompose"),
                     allowed_tools=("read_file", "list_files", "write_file"))


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
