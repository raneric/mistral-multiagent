import json
from types import SimpleNamespace

import pytest

from multiagent.discovery import (
    InterviewSession,
    run_discovery,
    validate_prompts,
)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(complete=self._complete)
        self.responses = list(responses)
        self.calls: list[dict] = []

    def _complete(self, **kwargs):
        self.calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        # Endless tool call: guarantees the max-turns path for misbehaving agents
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            tool_calls=[SimpleNamespace(
                id="x", function=SimpleNamespace(name="echo", arguments="{}"))],
            content=""))])


class EventSinkStub:
    def emit(self, *args, **kwargs) -> None:
        pass

    def close(self) -> None:
        pass


def make_msg(tool_calls=None, content=""):
    msg = SimpleNamespace(content=content)
    if tool_calls is not None:
        msg.tool_calls = [
            SimpleNamespace(id=f"call-{i}", function=SimpleNamespace(name=n, arguments=a))
            for i, (n, a) in enumerate(tool_calls)
        ]
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def make_settings(tmp_path):
    return SimpleNamespace(
        api_key="fake", workspace=tmp_path, pm_model="m", dev_model="m",
        reviewer_model="m", max_agent_turns=5, bash_timeout=10,
        prompts_dir=tmp_path / ".multiagent",
    )


def write_tool_factory(root):
    def write_file(path: str, content: str) -> str:
        (root / path).write_text(content, encoding="utf-8")
        return "ok"
    return write_file


def author_runner(settings, responses):
    """Real runner (sandboxed write_file) with a scripted LLM client. Returns (runner, client)."""
    from multiagent.llm.runner import AgentRunner
    from multiagent.tools import default_registry
    from multiagent.tools.sandbox import Workspace

    registry = default_registry(Workspace(settings.workspace), bash_timeout=10)
    client = FakeClient(responses)
    runner = AgentRunner(
        client, registry, EventSinkStub(),
        system_prompt="x", max_turns=5, agent_name="author",
    )
    return runner, client


def interviewer_runner(settings, responses):
    """Real runner with sandboxed write_file plus a live InterviewSession.ask_user."""
    from multiagent.discovery import InterviewSession
    from multiagent.llm.runner import AgentRunner
    from multiagent.tools import default_registry
    from multiagent.tools.sandbox import Workspace

    registry = default_registry(Workspace(settings.workspace), bash_timeout=10)
    registry.add(InterviewSession().ask_user)
    client = FakeClient(responses)
    runner = AgentRunner(
        client, registry, EventSinkStub(),
        system_prompt="x", max_turns=5, agent_name="interviewer",
    )
    return runner, client


def test_session_records_and_renders() -> None:
    session = InterviewSession()
    session.record("What language?", "Python, please")
    assert "What language?" in session.render()
    assert "Python, please" in session.render()
    assert "## Q1." in session.render()


def test_validate_prompts_missing_dir(tmp_path) -> None:
    violations = validate_prompts(tmp_path / ".multiagent")
    assert violations == [f"{tmp_path / '.multiagent'} does not exist - nothing was generated"]


def test_validate_prompts_all_missing(tmp_path) -> None:
    (tmp_path / ".multiagent").mkdir()
    violations = validate_prompts(tmp_path / ".multiagent")
    assert len(violations) == 5
    assert all("not generated" in v for v in violations)


def test_validate_prompts_marker_violation(tmp_path) -> None:
    overrides = tmp_path / ".multiagent"
    overrides.mkdir()
    ok = "# fine"
    (overrides / "conventions.md").write_text(ok)
    (overrides / "developer.md").write_text(ok)
    (overrides / "reviewer.md").write_text("## Verdict: PASS | FIX_REQUIRED")
    (overrides / "pm_fix.md").write_text("read {task_path} only")  # missing {report_path}
    (overrides / "pm_decompose.md").write_text("write to tasks/task-NNN.md, Depends on:")
    violations = validate_prompts(overrides)
    assert len(violations) == 1
    assert "pm_fix.md" in violations[0] and "{report_path}" in violations[0]


def test_validate_prompts_valid_set(tmp_path) -> None:
    overrides = tmp_path / ".multiagent"
    overrides.mkdir()
    (overrides / "conventions.md").write_text("# Project conventions")
    (overrides / "developer.md").write_text("# Dev")
    (overrides / "reviewer.md").write_text("## Verdict: PASS | FIX_REQUIRED\nnever fix code")
    (overrides / "pm_fix.md").write_text("Fix {task_path} per {report_path}")
    (overrides / "pm_decompose.md").write_text("Write tasks to tasks/task-NNN.md. Depends on:")
    assert validate_prompts(overrides) == []


def test_discovery_fails_without_spec_file(tmp_path) -> None:
    settings = make_settings(tmp_path)
    interviewer = interviewer_runner(settings, [make_msg(content="I asked nothing, sorry.")])[0]
    with pytest.raises(RuntimeError, match="spec.md"):
        run_discovery("a todo app", settings, events=EventSinkStub(), interviewer=interviewer)


def test_discovery_end_to_end_with_fakes(tmp_path) -> None:
    settings = make_settings(tmp_path)

    def spec_tool_call():
        return make_msg(tool_calls=[(
            "write_file",
            json.dumps({"path": "spec.md", "content": "# Spec: My App\n## Done when tests pass"}),
        )], content="spec is written")

    interviewer = interviewer_runner(
        settings, [spec_tool_call(), make_msg(content="summary")]
    )[0]
    # Author "forgets" to write anything -> validation must catch it and abort.
    author, fake_author = author_runner(settings, [make_msg(content="wrote the files (not really)")])
    with pytest.raises(RuntimeError, match="machine contracts"):
        run_discovery("a todo app", settings, events=EventSinkStub(),
                      interviewer=interviewer, author=author)
    # The author was retried with the violations embedded in the new task.
    user_messages = [
        m["content"]
        for call in fake_author.calls for m in call["messages"]
        if isinstance(m, dict) and m.get("role") == "user"
    ]
    assert any("Violations from your previous generation" in msg for msg in user_messages)
    # The author wrote nothing, so the report flagged the missing output directory.
    assert any("nothing was generated" in msg for msg in user_messages)


def test_discovery_generates_overrides_then_run_uses_them(tmp_path) -> None:
    settings = make_settings(tmp_path)
    overrides = ".multiagent"
    generated = {
        f"{overrides}/conventions.md": "# Conventions: Rust, cargo test",
        f"{overrides}/developer.md": "# Dev: run cargo test",
        f"{overrides}/reviewer.md": "## Verdict: PASS | FIX_REQUIRED",
        f"{overrides}/pm_fix.md": "Fix {task_path} per {report_path}",
        f"{overrides}/pm_decompose.md": "Write to tasks/task-NNN.md",
    }

    author = author_runner(settings, [
        _write_files_msg(generated),
        make_msg(content="generated 5 files"),
    ])[0]

    interviewer = interviewer_runner(settings, [
        make_msg(tool_calls=[(
            "write_file",
            json.dumps({"path": "spec.md", "content": "# Spec: My App"}),
        )], content="done"),
    ])[0]

    run_discovery("todo app", settings, events=EventSinkStub(),
                  interviewer=interviewer, author=author)

    assert (tmp_path / "spec.md").is_file()
    for name, content in generated.items():
        assert (settings.workspace / name).read_text() == content

    # And the build phase now resolves the generated prompts:
    from multiagent.agents.base import developer_spec
    assert developer_spec(settings).system_prompt == (
        "# Dev: run cargo test\n\n# Conventions: Rust, cargo test"
    )


def _write_files_msg(files: dict[str, str]):
    # multiple tool calls in one assistant message
    return make_msg(tool_calls=[
        ("write_file", json.dumps({"path": name, "content": body}))
        for name, body in files.items()
    ])
