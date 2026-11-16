"""Prompt templates: built-in defaults, overridable per project.

After a discovery phase, project-specific prompts and conventions are generated
under `<project>/.multiagent/`. `resolve()` picks them up when present; agents
building into this repo's default `workspace/` fall back to the built-ins here.
"""
from pathlib import Path

_DIR = Path(__file__).parent
BUILTIN_PROMPTS = ("developer", "reviewer", "pm_decompose", "pm_fix", "conventions")


def load(name: str) -> str:
    """Load a built-in template."""
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")


def resolve(name: str, overrides_dir: Path | None = None) -> str:
    """Project-generated override (overrides_dir/<name>.md) wins over built-in."""
    if overrides_dir is not None:
        candidate = Path(overrides_dir) / f"{name}.md"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return load(name)


def compose(*names: str, overrides_dir: Path | None = None) -> str:
    """Concatenate resolved templates; used to stack shared sections (e.g. conventions)."""
    return "\n\n".join(resolve(name, overrides_dir).rstrip("\n") for name in names)
