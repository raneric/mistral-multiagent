"""The agent loop, as an injectable class instead of a global function."""
import json
from dataclasses import dataclass, field

from multiagent.events import EventSink
from multiagent.llm.client import Mistral, complete_with_retry
from multiagent.tools.registry import ToolRegistry


@dataclass
class AgentResult:
    final_text: str
    turns: int
    tool_calls: int = 0
    stopped_reason: str = "completed"
    tool_log: list[dict] = field(default_factory=list)


class AgentRunner:
    """Runs one agent until it stops calling tools.

    Holds the client, the tools this agent may use, and an event sink so each
    loop step is observable and testable (inject a fake client).
    """

    def __init__(
        self,
        client: Mistral,
        registry: ToolRegistry,
        events: EventSink,
        system_prompt: str,
        max_turns: int = 25,
        agent_name: str = "agent",
    ):
        self.client = client
        self.registry = registry
        self.events = events
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.agent_name = agent_name

    def run(self, user_task: str, model: str) -> AgentResult:
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_task},
        ]
        result = AgentResult(final_text="", turns=0, stopped_reason="max_turns")

        for result.turns in range(1, self.max_turns + 1):
            resp = complete_with_retry(
                self.client,
                model=model,
                messages=messages,
                tools=self.registry.schemas(),
            )
            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                result.final_text = msg.content or ""
                result.stopped_reason = "completed"
                break

            messages.append(msg)
            for tc in tool_calls:
                name = tc.function.name
                raw = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw)
                except json.JSONDecodeError:
                    args = None
                if not isinstance(args, dict):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": (
                            f"malformed tool arguments (not valid JSON object): {raw[:200]}"
                        ),
                    })
                    self.events.emit(
                        "tool_error", agent=self.agent_name, message=f"bad args for {name}"
                    )
                    continue
                result.tool_calls += 1
                self.events.emit(
                    "tool_call", agent=self.agent_name, message=f"{name}({', '.join(args)})"
                )
                output = self.registry.call(name, args)
                result.tool_log.append({"name": name, "args": args})
                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": output,
                    "tool_call_id": tc.id,
                })

        self.events.emit(
            "agent_done",
            agent=self.agent_name,
            message=f"turns={result.turns} tools={result.tool_calls} reason={result.stopped_reason}",
        )
        return result
