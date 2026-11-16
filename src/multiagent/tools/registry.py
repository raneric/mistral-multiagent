"""Tool registry: one source of truth for implementations and JSON schemas."""
import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    type(None): "null",
}


@dataclass
class Tool:
    name: str
    fn: Callable
    schema: dict


def schema_from_function(fn: Callable) -> dict:
    """Build a Mistral/OpenAI-style function schema from a function's signature."""
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        json_type = _JSON_TYPES.get(param.annotation, "string")
        properties[param_name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    doc = (inspect.getdoc(fn) or fn.__name__).strip().splitlines()
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": doc[0] if doc else fn.__name__,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def add(self, fn: Callable) -> None:
        self._tools[fn.__name__] = Tool(fn.__name__, fn, schema_from_function(fn))

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict]:
        return [t.schema for t in self._tools.values()]

    def restrict(self, names: list[str]) -> "ToolRegistry":
        """A new registry containing only the named tools."""
        restricted = ToolRegistry()
        for name in names:
            if name not in self._tools:
                raise KeyError(f"unknown tool: {name}")
            restricted._tools[name] = self._tools[name]
        return restricted

    def call(self, name: str, args: dict) -> str:
        """Execute a tool and return its result as text. Errors become model-readable text."""
        tool = self._tools.get(name)
        if tool is None:
            return f"unknown tool: {name}"
        try:
            return str(tool.fn(**args))
        except TypeError as e:
            return f"malformed arguments for {name}: {e}"
        except Exception as e:  # returned to the model so it can react, not crash the run
            return f"tool '{name}' failed: {type(e).__name__}: {e}"
