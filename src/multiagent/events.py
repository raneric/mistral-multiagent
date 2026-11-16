"""Structured run events, written as JSONL and echoed to the console."""
import json
from datetime import datetime, timezone
from pathlib import Path


class EventSink:
    def __init__(self, log_path: Path | None = None, echo: bool = True):
        self._log_path = log_path
        self._echo = echo
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = log_path.open("a", encoding="utf-8")
        else:
            self._fh = None

    def emit(self, kind: str, **data) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **data}
        line = json.dumps(event, ensure_ascii=False)
        if self._fh is not None:
            self._fh.write(line + "\n")
            self._fh.flush()
        if self._echo:
            who = data.get("agent", kind)
            msg = data.get("message")
            print(f"[{who}] {msg}" if msg else f"[{who}] {kind}")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
