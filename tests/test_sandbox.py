from pathlib import Path

import pytest

from multiagent.tools.filesystem import register_filesystem_tools
from multiagent.tools.registry import ToolRegistry
from multiagent.tools.sandbox import SandboxError, Workspace


@pytest.fixture()
def ws(tmp_path: Path) -> Workspace:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("print('hi')\n")
    return Workspace(root)


def test_resolve_keeps_paths_inside_root(ws: Workspace) -> None:
    assert ws.resolve("src/app.py").name == "app.py"
    assert ws.resolve(".").is_dir()


def test_rejects_parent_escape(ws: Workspace) -> None:
    with pytest.raises(SandboxError):
        ws.resolve("../outside.txt")


def test_rejects_sibling_prefix_escape(ws: Workspace, tmp_path: Path) -> None:
    # Regression: 'workspace2' must not pass a startswith(root) check.
    sibling = tmp_path / "workspace2"
    sibling.mkdir()
    with pytest.raises(SandboxError):
        ws.resolve("../workspace2/secret.txt")


def test_rejects_symlink_escape(ws: Workspace, tmp_path: Path) -> None:
    link = ws.root / "link.loc"
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SandboxError):
        ws.resolve("link.loc/secret.txt")


def test_file_roundtrip(ws: Workspace) -> None:
    reg = ToolRegistry()
    register_filesystem_tools(reg, ws)
    assert "wrote" in reg.call("write_file", {"path": "docs/a.md", "content": "hello"})
    assert reg.call("read_file", {"path": "docs/a.md"}) == "hello"
    listing = reg.call("list_files", {})
    assert "docs/a.md" in listing and "src/app.py" in listing
    assert "__pycache__" not in listing
