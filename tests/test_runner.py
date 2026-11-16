import json
from types import SimpleNamespace

from multiagent.events import EventSink
from multiagent.llm.runner import AgentRunner
from multiagent.tools.registry import ToolRegistry


class FakeClient:
    """Stands in for Mistral client.chat.complete."""

    def __init__(self, responses):
        self.chat = SimpleNamespace(complete=self._complete)
        self.responses = list(responses)
        self.calls: list[dict] = []

    def _complete(self, **kwargs):
        self.calls.append(kwargs)
        # Beyond the scripted responses, keep issuing a tool call forever
        # (exercises the max-turns path).
        if self.responses:
            return self.responses.pop(0)
        return make_msg(tool_calls=[("echo", json.dumps({"x": "again"}))])


def make_msg(tool_calls=None, content=""):
    msg = SimpleNamespace(content=content)
    if tool_calls is not None:
        msg.tool_calls = [
            SimpleNamespace(id=f"call-{i}", function=SimpleNamespace(name=name, arguments=args))
            for i, (name, args) in enumerate(tool_calls)
        ]
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_completes_after_tool_call(tmp_path):
    events = EventSink(None, echo=False)
    reg = ToolRegistry()

    def write_file(path: str, content: str) -> str:
        return "ok"

    reg.add(write_file)

    tool_call = make_msg(tool_calls=[("write_file", json.dumps({"path": "a.txt", "content": "hi"}))])
    final = make_msg(content="all done")
    client = FakeClient([tool_call, final])

    runner = AgentRunner(client, reg, events, system_prompt="sys", max_turns=5)
    result = runner.run("task", "some-model")

    assert result.final_text == "all done"
    assert result.stopped_reason == "completed"
    assert result.tool_calls == 1
    assert result.tool_log == [{"name": "write_file", "args": {"path": "a.txt", "content": "hi"}}]
    # tool answer was appended with the right tool_call_id for the API
    second_request = client.calls[1]["messages"]
    assert any(m.get("tool_call_id") == "call-0" for m in second_request if isinstance(m, dict))


def test_malformed_tool_args_do_not_crash(tmp_path):
    events = EventSink(None, echo=False)
    reg = ToolRegistry()

    def write_file(path: str, content: str) -> str:
        return "ok"

    reg.add(write_file)
    broken = make_msg(tool_calls=[("write_file", "{not valid json")])
    final = make_msg(content="gave up nicely")
    client = FakeClient([broken, final])

    runner = AgentRunner(client, reg, events, system_prompt="sys", max_turns=5)
    result = runner.run("task", "some-model")

    assert result.final_text == "gave up nicely"
    tool_feedback = [
        m["content"] for m in client.calls[1]["messages"]
        if isinstance(m, dict) and m.get("role") == "tool"
    ]
    assert any("malformed" in c for c in tool_feedback)


def test_max_turns_is_reported():
    events = EventSink(None, echo=False)
    runner = AgentRunner(FakeClient([]), ToolRegistry(), events,
                         system_prompt="sys", max_turns=2)
    result = runner.run("task", "some-model")
    assert result.stopped_reason == "max_turns"
    assert result.turns == 2
