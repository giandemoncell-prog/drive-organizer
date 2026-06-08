from __future__ import annotations

import queue
import time
import uuid


class _FakeProgress:
    def __init__(self, q: queue.Queue, total: int, interval: int = 50):
        self._q = q
        self._total = total
        self._done = 0
        self._interval = interval

    def update(self, task_id, advance: int = 1) -> None:
        self._done += advance
        if self._done % self._interval == 0 or self._done >= self._total:
            self._q.put({"type": "progress", "current": self._done, "total": self._total,
                         "message": f"Elaborati {self._done}/{self._total}…"})

    def advance(self, task_id, advance: int = 1) -> None:
        self.update(task_id, advance)


def new_op() -> tuple[str, queue.Queue]:
    from web_app.state import _ops, _ops_ts
    op_id = uuid.uuid4().hex
    q: queue.Queue = queue.Queue()
    _ops[op_id] = q
    _ops_ts[op_id] = time.monotonic()
    return op_id, q


def build_cascade():
    from drive_organizer.ai.factory import build_cascade as _bc
    return _bc()


def sanitize_key(v: str) -> str:
    """Strip newlines/CR to prevent .env injection."""
    return v.replace("\n", "").replace("\r", "").strip()
