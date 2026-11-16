"""Tool package: registry + concrete toolsets."""
from multiagent.tools.registry import ToolRegistry
from multiagent.tools.sandbox import Workspace


def default_registry(ws: Workspace, bash_timeout: int = 120) -> ToolRegistry:
    """Full toolset available to agents (filesystem + shell)."""
    from multiagent.tools import filesystem, shell

    registry = ToolRegistry()
    filesystem.register_filesystem_tools(registry, ws)
    shell.register_shell_tool(registry, ws, timeout=bash_timeout)
    return registry
