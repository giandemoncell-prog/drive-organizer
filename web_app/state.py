from __future__ import annotations

import queue
import threading

# SSE operation queues: op_id → Queue of event dicts
_ops: dict[str, queue.Queue] = {}
_ops_ts: dict[str, float] = {}  # creation timestamp for TTL cleanup

# Structure cache (current Drive tree)
_structure_lock = threading.Lock()
_structure_loading = False
_structure_cache: dict | None = None

# Pending organize plans (for export): op_id → OrganizationPlan
_plans: dict = {}
