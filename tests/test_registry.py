import json

import pytest

from multiagent.tools.registry import ToolRegistry


def make_two_tool_registry() -> ToolRegistry:
    reg = ToolRegistry()

    def read_file(path: str) -> str:
        """Read a text file from the workspace."""
        return path

    def noop(x: int = 1) -> int:
        return x

    reg.add(read_file)
    reg.add(noop)
    return reg


def test_schema_built_from_signature() -> None:
    reg = make_two_tool_registry()
    files = {t["function"]["name"]: t for t in reg.schemas()}
    assert files["read_file"]["function"]["parameters"]["required"] == ["path"]
    assert files["read_file"]["function"]["description"] == (
        "Read a text file from the workspace."
    )
    assert files["noop"]["function"]["parameters"]["required"] == []
    assert files["noop"]["function"]["parameters"]["properties"]["x"]["type"] == "integer"
    assert json.dumps(files)  # schemas are JSON-serializable


def test_unknown_tool_returns_text_not_exception() -> None:
    reg = make_two_tool_registry()
    out = reg.call("delete_everything", {})
    assert out.startswith("unknown tool")


def test_tool_exception_becomes_model_readable_text() -> None:
    reg = ToolRegistry()

    def boom(x: int) -> str:
        raise OSError("disk full")

    reg.add(boom)
    out = reg.call("boom", {"x": 1})
    assert "OSError" in out and "disk full" in out


def test_malformed_arguments_are_handled() -> None:
    reg = make_two_tool_registry()
    out = reg.call("noop", {"x": "not-an-int-function-payload-fine"})
    # str coerces; the point is it must not raise out of the registry
    assert out != "unknown tool: noop"


def test_restrict_selects_subset_and_rejects_unknown() -> None:
    reg = make_two_tool_registry()
    restricted = reg.restrict(["read_file"])
    assert restricted.names() == ["read_file"]


def test_restrict_rejects_unknown_name() -> None:
    reg = make_two_tool_registry()
    with pytest.raises(KeyError):
        reg.restrict(["nonexistent"])
