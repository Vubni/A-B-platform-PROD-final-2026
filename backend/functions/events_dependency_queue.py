from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import EVENTS_DEPENDENCY_MAX_DELAY_DAYS


@dataclass
class PendingEvent:
    event_id: str
    decision_id: str
    event_type_id: str
    subject_id: str
    timestamp: datetime
    payload: Optional[Dict[str, Any]]
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_insert_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "decision_id": self.decision_id,
            "event_type_id": self.event_type_id,
            "subject_id": self.subject_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


class EventsDependencyQueue:

    def __init__(self, max_delay_days: Optional[int] = None) -> None:
        self._max_delay_days = max_delay_days if max_delay_days is not None else EVENTS_DEPENDENCY_MAX_DELAY_DAYS
        self._pending: Dict[Tuple[str, str], List[PendingEvent]] = {}
        self._lock = asyncio.Lock()

    def _cutoff(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=self._max_delay_days)

    async def add(
        self,
        decision_id: str,
        required_show_event_type_id: str,
        event: PendingEvent,
    ) -> None:
        async with self._lock:
            key = (decision_id, required_show_event_type_id)
            if key not in self._pending:
                self._pending[key] = []
            self._pending[key].append(event)

    async def pop_ready(
        self,
        decision_id: str,
        show_event_type_id: str,
    ) -> List[PendingEvent]:
        async with self._lock:
            key = (decision_id, show_event_type_id)
            events = self._pending.pop(key, [])
            return events

    async def expire_old(self) -> int:
        cutoff = self._cutoff()
        removed = 0
        async with self._lock:
            keys_to_drop: List[Tuple[str, str]] = []
            for key, events in self._pending.items():
                kept: List[PendingEvent] = []
                for e in events:
                    if e.queued_at >= cutoff:
                        kept.append(e)
                    else:
                        removed += 1
                if kept:
                    self._pending[key] = kept
                else:
                    keys_to_drop.append(key)
            for k in keys_to_drop:
                del self._pending[k]
        return removed

    async def size(self) -> int:
        async with self._lock:
            return sum(len(events) for events in self._pending.values())


events_dependency_queue = EventsDependencyQueue()
