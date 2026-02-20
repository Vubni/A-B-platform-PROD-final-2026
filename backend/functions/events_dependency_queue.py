from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from config import EVENTS_DEPENDENCY_MAX_DELAY_DAYS


@dataclass
class PendingEvent:
    event_id: str
    decision_id: str
    event_type_id: str
    subject_id: str
    timestamp: datetime
    payload: dict[str, Any] | None
    queued_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_insert_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "decision_id": self.decision_id,
            "event_type_id": self.event_type_id,
            "subject_id": self.subject_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


class EventsDependencyQueue:
    def __init__(self, max_delay_days: int | None = None) -> None:
        self._max_delay_days = (
            max_delay_days if max_delay_days is not None else EVENTS_DEPENDENCY_MAX_DELAY_DAYS
        )
        self._pending: dict[tuple[str, str], list[PendingEvent]] = {}
        self._lock = asyncio.Lock()

    def _cutoff(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self._max_delay_days)

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
    ) -> list[PendingEvent]:
        async with self._lock:
            key = (decision_id, show_event_type_id)
            events = self._pending.pop(key, [])
            return events

    async def expire_old(self) -> int:
        cutoff = self._cutoff()
        removed = 0
        async with self._lock:
            keys_to_drop: list[tuple[str, str]] = []
            for key, events in self._pending.items():
                kept: list[PendingEvent] = []
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
