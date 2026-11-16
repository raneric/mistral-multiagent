"""Shell tool for running tests/linters inside the workspace."""
import subprocess

from multiagent.tools.registry import ToolRegistry
from multiagent.tools.sandbox import Workspace


def register_shell_tool(registry: ToolRegistry, ws: Workspace, timeout: int = 120) -> None:
    def run_bash(command: str) -> str:
        """Run a shell command in the workspace root (e.g. pytest, ruff check)."""
        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=ws.root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,  # exit codes are reported to the model, not raised
            )
        except subprocess.TimeoutExpired:
            return f"exit_code=124 (timeout after {timeout}s)"
        output = (r.stdout or "") + (r.stderr or "")
        return f"exit_code={r.returncode}\n{output[-4000:]}"

    registry.add(run_bash)
