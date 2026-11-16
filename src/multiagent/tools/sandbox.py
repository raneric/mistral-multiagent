"""Workspace sandbox: every agent tool path is resolved against the workspace root."""
from pathlib import Path


class SandboxError(ValueError):
    """Raised when a path escapes the workspace."""


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def resolve(self, path: str | Path) -> Path:
        candidate = (self.root / path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise SandboxError(f"path escapes workspace: {path}")
        return candidate

    def __repr__(self) -> str:
        return f"Workspace({str(self.root)!r})"
