from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from core import parse_iso_timestamp
from config import EVENTS_DEPENDENCY_MAX_DELAY_DAYS
from database.database import Database


@dataclass
class PendingEvent:
    event_id: str
    decision_id: str
    event_type_id: str
    subject_id: str
    timestamp: datetime
    payload: dict[str, Any] | None
    queued_at: datetime | None = None

    def to_insert_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "decision_id": self.decision_id,
            "event_type_id": self.event_type_id,
            "subject_id": self.subject_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


def _row_to_pending_event(row: dict[str, Any]) -> PendingEvent:
    ts_val = row.get("timestamp")
    ts, _ = parse_iso_timestamp(ts_val)
    queued_val = row.get("queued_at")
    queued_at, _ = parse_iso_timestamp(queued_val) if queued_val is not None else (None, None)
    return PendingEvent(
        event_id=str(row["event_id"]),
        decision_id=str(row["decision_id"]),
        event_type_id=str(row["event_type_id"]),
        subject_id=str(row["subject_id"]),
        timestamp=ts or datetime.now(UTC),
        payload=row.get("payload"),
        queued_at=queued_at,
    )


class EventsDependencyQueue:
    def __init__(self, max_delay_days: int | None = None) -> None:
        self._max_delay_days = (
            max_delay_days if max_delay_days is not None else EVENTS_DEPENDENCY_MAX_DELAY_DAYS
        )

    def _cutoff(self) -> datetime:
        return datetime.now(UTC) - timedelta(days=self._max_delay_days)

    async def add(
        self,
        decision_id: str,
        required_show_event_type_id: str,
        event: PendingEvent,
    ) -> None:
        async with Database() as db:
            await db.execute(
                """INSERT INTO events_dependency_queue
                   (decision_id, required_show_event_type_id, event_id, event_type_id, subject_id, "timestamp", payload)
                   VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5, $6, $7)""",
                (
                    decision_id,
                    required_show_event_type_id,
                    event.event_id,
                    event.event_type_id,
                    event.subject_id,
                    event.timestamp,
                    json.dumps(event.payload) if event.payload is not None else None,
                ),
            )

    async def pop_ready(
        self,
        decision_id: str,
        show_event_type_id: str,
    ) -> list[PendingEvent]:
        async with Database() as db:
            rows = await db.execute_all(
                """SELECT event_id, decision_id, event_type_id, subject_id, "timestamp", payload, queued_at
                   FROM events_dependency_queue
                   WHERE decision_id = $1::uuid AND required_show_event_type_id = $2::uuid""",
                (decision_id, show_event_type_id),
            )
            if not rows:
                return []
            await db.execute(
                """DELETE FROM events_dependency_queue
                   WHERE decision_id = $1::uuid AND required_show_event_type_id = $2::uuid""",
                (decision_id, show_event_type_id),
            )
            return [_row_to_pending_event(r) for r in rows]

    async def expire_old(self) -> int:
        cutoff = self._cutoff()
        async with Database() as db:
            count_row = await db.execute(
                "SELECT COUNT(*) AS n FROM events_dependency_queue WHERE queued_at < $1",
                (cutoff,),
            )
            removed = int(count_row["n"]) if count_row else 0
            await db.execute(
                "DELETE FROM events_dependency_queue WHERE queued_at < $1",
                (cutoff,),
            )
        return removed

    async def size(self) -> int:
        async with Database() as db:
            row = await db.execute("SELECT COUNT(*) AS n FROM events_dependency_queue")
            return int(row["n"]) if row else 0


events_dependency_queue = EventsDependencyQueue()
