"""Environment-driven settings, validated once at load time."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load ./.env from the current working directory (conventional CLI behavior),
# not from the installed package location.
load_dotenv(Path.cwd() / ".env")


@dataclass(frozen=True)
class Settings:
    api_key: str
    workspace: Path
    max_agent_turns: int = 25
    max_fix_cycles: int = 2
    max_workers: int = 3
    bash_timeout: int = 120
    pm_model: str = "mistral-large-latest"
    dev_model: str = "mistral-small-latest"
    reviewer_model: str = "mistral-large-latest"

    @property
    def tasks_dir(self) -> Path:
        return self.workspace / "tasks"

    @property
    def reports_dir(self) -> Path:
        return self.workspace / "reports"

    @property
    def prompts_dir(self) -> Path:
        """Project-generated prompt/convention overrides (discovery phase writes here)."""
        return self.workspace / ".multiagent"

    @classmethod
    def load(cls) -> "Settings":
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError(
                "MISTRAL_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        workspace = Path(
            os.environ.get("AGENT_WORKSPACE") or "workspace"
        ).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return cls(
            api_key=api_key,
            workspace=workspace,
            max_agent_turns=int(os.environ.get("MAX_AGENT_TURNS", "25")),
            max_fix_cycles=int(os.environ.get("MAX_FIX_CYCLES", "2")),
            max_workers=int(os.environ.get("MAX_WORKERS", "3")),
            bash_timeout=int(os.environ.get("BASH_TIMEOUT", "120")),
            pm_model=os.environ.get("PM_MODEL", "mistral-large-latest"),
            dev_model=os.environ.get("DEV_MODEL", "mistral-small-latest"),
            reviewer_model=os.environ.get("REVIEWER_MODEL", "mistral-large-latest"),
        )
