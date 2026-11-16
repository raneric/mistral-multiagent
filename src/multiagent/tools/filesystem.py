"""Filesystem tools; every path is confined to the workspace."""
import os

from multiagent.tools.registry import ToolRegistry
from multiagent.tools.sandbox import Workspace


def register_filesystem_tools(registry: ToolRegistry, ws: Workspace) -> None:
    def read_file(path: str) -> str:
        """Read a text file from the workspace."""
        full = ws.resolve(path)
        return full.read_text(encoding="utf-8")

    def write_file(path: str, content: str) -> str:
        """Create or overwrite a text file in the workspace."""
        full = ws.resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"wrote {path} ({len(content)} chars)"

    def list_files(path: str = ".") -> str:
        """List all files in the workspace, relative to its root."""
        full = ws.resolve(path)
        ignore = {".git", "__pycache__", "node_modules", ".venv"}
        out = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in ignore]
            for name in sorted(files):
                out.append(os.path.relpath(os.path.join(root, name), ws.root))
        return "\n".join(sorted(out)) or "(empty)"

    registry.add(read_file)
    registry.add(write_file)
    registry.add(list_files)
