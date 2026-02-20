from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core import parse_iso_timestamp, validate_uuid
from database.database import Database
from functions.event_types import get_event_type_by_key
from functions.events_dependency_queue import (
    PendingEvent,
    events_dependency_queue,
)
from functions.guardrails import check_guardrails_for_decisions


@dataclass
class EventSubmitInput:
    event_id: str
    decision_id: str
    event_type_key: str
    subject_id: str
    timestamp: datetime
    payload: dict[str, Any] | None


def _validate_required_params(required_params: dict | None, payload: dict | None) -> str | None:
    if not required_params or not isinstance(required_params, dict):
        return None
    pl = payload if isinstance(payload, dict) else {}
    for key, type_hint in required_params.items():
        if key not in pl:
            return f"missing required param: {key}"
        val = pl[key]
        th = (type_hint or "string").lower()
        if th == "number":
            if not isinstance(val, (int, float)):
                return f"param '{key}' must be number"
        elif th == "string":
            if not isinstance(val, str):
                return f"param '{key}' must be string"
        elif th == "bool":
            if not isinstance(val, bool):
                return f"param '{key}' must be bool"
    return None


def _validate_single_event(
    raw: Any, index: int
) -> tuple[EventSubmitInput | None, str | None, str | None]:
    if not isinstance(raw, dict):
        return None, None, "event must be an object"
    ev_id = raw.get("event_id")
    if not ev_id or not str(ev_id).strip():
        return None, str(ev_id) if ev_id is not None else None, "event_id is required"
    ev_id = str(ev_id).strip()

    dec_id = raw.get("decision_id")
    if not dec_id:
        return None, ev_id, "decision_id is required"
    dec_uuid = validate_uuid(str(dec_id))
    if not dec_uuid:
        return None, ev_id, "decision_id must be a valid UUID"

    et_key = raw.get("event_type_key")
    if not et_key or not str(et_key).strip():
        return None, ev_id, "event_type_key is required"

    subj = raw.get("subject_id")
    if subj is None or (isinstance(subj, str) and not subj.strip()):
        return None, ev_id, "subject_id is required"
    subj = str(subj).strip()

    ts, ts_err = parse_iso_timestamp(raw.get("timestamp"))
    if ts_err:
        return None, ev_id, ts_err

    payload = raw.get("payload")
    if payload is not None and not isinstance(payload, dict):
        return None, ev_id, "payload must be an object"
    if payload is None:
        payload = {}

    return (
        EventSubmitInput(
            event_id=ev_id,
            decision_id=dec_uuid,
            event_type_key=str(et_key).strip(),
            subject_id=subj,
            timestamp=ts,
            payload=payload or None,
        ),
        ev_id,
        None,
    )


async def _decision_exists(decision_id: str) -> bool:
    async with Database() as db:
        row = await db.execute("SELECT 1 FROM decisions WHERE decision_id = $1", (decision_id,))
        return bool(row)


async def _event_exists(event_id: str) -> bool:
    async with Database() as db:
        row = await db.execute("SELECT 1 FROM event_occurrences WHERE event_id = $1", (event_id,))
        return bool(row)


async def _show_event_exists(decision_id: str, show_event_type_id: str) -> bool:
    async with Database() as db:
        row = await db.execute(
            """SELECT 1 FROM event_occurrences
               WHERE decision_id = $1 AND event_type_id = $2
               LIMIT 1""",
            (decision_id, show_event_type_id),
        )
        return bool(row)


async def _insert_event(
    event_id: str,
    decision_id: str,
    event_type_id: str,
    subject_id: str,
    timestamp: datetime,
    payload: dict | None,
) -> bool:
    async with Database() as db:
        try:
            await db.execute(
                """INSERT INTO event_occurrences
                   (event_id, decision_id, event_type_id, subject_id, "timestamp", payload)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                (
                    event_id,
                    decision_id,
                    event_type_id,
                    subject_id,
                    timestamp,
                    json.dumps(payload) if payload else None,
                ),
            )
            return True
        except Exception:
            return False


async def process_events_batch(events: list[Any]) -> dict[str, Any]:
    accepted = 0
    duplicates = 0
    rejected = 0
    errors: list[dict[str, Any]] = []
    touched_decision_ids: set[str] = set()

    await events_dependency_queue.expire_old()

    for index, raw in enumerate(events):
        parsed, ev_id, err = _validate_single_event(raw, index)
        if err:
            rejected += 1
            errors.append(
                {
                    "index": index,
                    "event_id": ev_id,
                    "message": err,
                }
            )
            continue

        event_type = await get_event_type_by_key(parsed.event_type_key)
        if not event_type:
            rejected += 1
            errors.append(
                {
                    "index": index,
                    "event_id": parsed.event_id,
                    "message": f"unknown event type: {parsed.event_type_key}",
                }
            )
            continue

        if not await _decision_exists(parsed.decision_id):
            rejected += 1
            errors.append(
                {
                    "index": index,
                    "event_id": parsed.event_id,
                    "message": "decision_id not found",
                }
            )
            continue

        rp_err = _validate_required_params(event_type.get("required_params"), parsed.payload)
        if rp_err:
            rejected += 1
            errors.append(
                {
                    "index": index,
                    "event_id": parsed.event_id,
                    "message": rp_err,
                }
            )
            continue

        if await _event_exists(parsed.event_id):
            duplicates += 1
            continue

        et_id = event_type["id"]
        requires_show_id = event_type.get("requires_show_event_type_id")

        if requires_show_id:
            if await _show_event_exists(parsed.decision_id, requires_show_id):
                ok = await _insert_event(
                    parsed.event_id,
                    parsed.decision_id,
                    et_id,
                    parsed.subject_id,
                    parsed.timestamp,
                    parsed.payload,
                )
                if ok:
                    accepted += 1
                    touched_decision_ids.add(parsed.decision_id)
                else:
                    duplicates += 1
            else:
                pending = PendingEvent(
                    event_id=parsed.event_id,
                    decision_id=parsed.decision_id,
                    event_type_id=et_id,
                    subject_id=parsed.subject_id,
                    timestamp=parsed.timestamp,
                    payload=parsed.payload,
                )
                await events_dependency_queue.add(
                    parsed.decision_id,
                    requires_show_id,
                    pending,
                )
                accepted += 1
        else:
            ok = await _insert_event(
                parsed.event_id,
                parsed.decision_id,
                et_id,
                parsed.subject_id,
                parsed.timestamp,
                parsed.payload,
            )
            if ok:
                accepted += 1
                touched_decision_ids.add(parsed.decision_id)
                ready = await events_dependency_queue.pop_ready(
                    parsed.decision_id,
                    et_id,
                )
                for pe in ready:
                    await _insert_event(
                        pe.event_id,
                        pe.decision_id,
                        pe.event_type_id,
                        pe.subject_id,
                        pe.timestamp,
                        pe.payload,
                    )
                    touched_decision_ids.add(pe.decision_id)
            else:
                duplicates += 1

    if touched_decision_ids:
        try:
            await check_guardrails_for_decisions(list(touched_decision_ids))
        except Exception:
            pass

    return {
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": rejected,
        "errors": errors,
    }
