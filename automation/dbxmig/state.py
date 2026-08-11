"""Append-only run journal.

A metastore migration is a long-running batch that will be interrupted -- a
token expires, a warehouse restarts, someone's laptop sleeps. Without a journal
the only recovery is "run it all again and hope every statement was idempotent".

The journal records one JSON line per step outcome. Re-running the same plan
against the same journal skips steps already recorded as ``done``, so recovery
is the same command, not a different one. It is also the audit artifact: who ran
what, against which target, in what order, and what the workspace said back.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Set

STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
STATUS_BLOCKED = "blocked"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class JournalEntry:
    step_id: str
    status: str
    at: str = ""
    detail: str = ""
    statement: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "at": self.at or _utc_now(),
            "detail": self.detail,
            "statement": self.statement,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "JournalEntry":
        return cls(
            step_id=raw.get("step_id", ""),
            status=raw.get("status", ""),
            at=raw.get("at", ""),
            detail=raw.get("detail", ""),
            statement=raw.get("statement", ""),
            error=raw.get("error", ""),
        )


@dataclass
class Journal:
    """JSONL-backed run state. Opened per run, appended to, never rewritten."""

    path: str
    run_id: str = ""
    _entries: List[JournalEntry] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._entries = list(self._read())

    def _read(self) -> Iterator[JournalEntry]:
        if not self.path or not os.path.exists(self.path):
            return iter(())
        entries: List[JournalEntry] = []
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(JournalEntry.from_dict(json.loads(line)))
                except ValueError:
                    # A truncated final line is expected after a hard kill.
                    continue
        return iter(entries)

    def record(
        self,
        step_id: str,
        status: str,
        detail: str = "",
        statement: str = "",
        error: str = "",
    ) -> JournalEntry:
        entry = JournalEntry(
            step_id=step_id,
            status=status,
            at=_utc_now(),
            detail=detail,
            statement=statement,
            error=error,
        )
        self._entries.append(entry)
        if self.path:
            directory = os.path.dirname(os.path.abspath(self.path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
        return entry

    def completed(self) -> Set[str]:
        """Steps that finished successfully.

        A step that later failed is *not* completed even if an earlier attempt
        succeeded -- the last word for a step id wins.
        """
        last: Dict[str, str] = {}
        for entry in self._entries:
            last[entry.step_id] = entry.status
        return {step_id for step_id, status in last.items() if status == STATUS_DONE}

    def failures(self) -> List[JournalEntry]:
        last: Dict[str, JournalEntry] = {}
        for entry in self._entries:
            last[entry.step_id] = entry
        return [e for e in last.values() if e.status == STATUS_FAILED]

    def entries(self) -> List[JournalEntry]:
        return list(self._entries)

    def is_done(self, step_id: str) -> bool:
        return step_id in self.completed()

    def stats(self) -> Dict[str, int]:
        last: Dict[str, str] = {}
        for entry in self._entries:
            last[entry.step_id] = entry.status
        out: Dict[str, int] = {}
        for status in last.values():
            out[status] = out.get(status, 0) + 1
        return out


def resume_filter(journal: Optional[Journal]) -> Callable[[str], bool]:
    """Predicate that keeps only steps not already completed."""
    if journal is None:
        return lambda step_id: True
    done = journal.completed()
    return lambda step_id: step_id not in done
