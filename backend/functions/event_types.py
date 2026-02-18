from typing import Optional, List, Tuple

from database.database import Database
from core import serialize_json
import json


async def list_event_types(status: Optional[str] = None) -> List[dict]:
    async with Database() as db:
        if status and status in ("active", "archived"):
            rows = await db.execute_all(
                """SELECT id, key, display_name, description, required_params, validation_type,
                          report_alert_config, status, requires_show_event_type_id, is_critical,
                          created_at, updated_at
                   FROM event_types WHERE status = $1 ORDER BY key""",
                (status,),
            )
        else:
            rows = await db.execute_all(
                """SELECT id, key, display_name, description, required_params, validation_type,
                          report_alert_config, status, requires_show_event_type_id, is_critical,
                          created_at, updated_at
                   FROM event_types ORDER BY key"""
            )
        return serialize_json(rows)


async def get_event_type_by_id(type_id: str) -> Optional[dict]:
    async with Database() as db:
        if not db:
            return None
        row = await db.execute(
            """SELECT id, key, display_name, description, required_params, validation_type,
                      report_alert_config, status, requires_show_event_type_id, is_critical,
                      created_at, updated_at
               FROM event_types WHERE id = $1""",
            (type_id,),
        )
        return serialize_json(row) if row else None


async def create_event_type(key: str, display_name: Optional[str] = None, description: Optional[str] = None,
    required_params: Optional[dict] = None, validation_type: Optional[str] = None, report_alert_config: Optional[dict] = None,
    requires_show_event_type_id: Optional[str] = None, is_critical: bool = False) -> Tuple[Optional[dict], Optional[str]]:
    async with Database() as db:
        existing = await db.execute("SELECT id FROM event_types WHERE key = $1", (key,))
        if existing:
            return None, "duplicate_key"
        if requires_show_event_type_id:
            ref = await db.execute(
                "SELECT id FROM event_types WHERE id = $1 AND status = 'active'",
                (requires_show_event_type_id,),
            )
            if not ref:
                return None, "invalid_requires_show"
        await db.execute(
            """INSERT INTO event_types (key, display_name, description, required_params, validation_type,
                   report_alert_config, requires_show_event_type_id, is_critical)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
            (
                key,
                display_name,
                description,
                json.dumps(required_params),
                validation_type,
                json.dumps(report_alert_config),
                requires_show_event_type_id,
                is_critical,
            ),
        )
        row = await db.execute(
            """SELECT id, key, display_name, description, required_params, validation_type,
                      report_alert_config, status, requires_show_event_type_id, is_critical,
                      created_at, updated_at
               FROM event_types WHERE key = $1""",
            (key,),
        )
        if not row:
            return None, "db_error"
        return serialize_json(row), None


async def update_event_type(type_id: str, display_name: Optional[str] = None,
    description: Optional[str] = None, required_params: Optional[dict] = None, validation_type: Optional[str] = None, 
    report_alert_config: Optional[dict] = None, requires_show_event_type_id: Optional[str] = None, is_critical: Optional[bool] = None) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute("SELECT id FROM event_types WHERE id = $1", (type_id,))
        if not row:
            return None, "not_found"
        if requires_show_event_type_id is not None and requires_show_event_type_id == type_id:
            return None, "self_reference"
        if requires_show_event_type_id:
            ref = await db.execute(
                "SELECT id FROM event_types WHERE id = $1 AND status = 'active'",
                (requires_show_event_type_id,),
            )
            if not ref:
                return None, "invalid_requires_show"
        updates = []
        params = []
        pos = 1
        if display_name is not None:
            updates.append(f"display_name = ${pos}")
            params.append(display_name)
            pos += 1
        if description is not None:
            updates.append(f"description = ${pos}")
            params.append(description)
            pos += 1
        if required_params is not None:
            updates.append(f"required_params = ${pos}")
            params.append(required_params)
            pos += 1
        if validation_type is not None:
            updates.append(f"validation_type = ${pos}")
            params.append(validation_type)
            pos += 1
        if report_alert_config is not None:
            updates.append(f"report_alert_config = ${pos}")
            params.append(report_alert_config)
            pos += 1
        if requires_show_event_type_id is not None:
            updates.append(f"requires_show_event_type_id = ${pos}")
            params.append(requires_show_event_type_id)
            pos += 1
        if is_critical is not None:
            updates.append(f"is_critical = ${pos}")
            params.append(is_critical)
            pos += 1
        if not updates:
            out = await get_event_type_by_id(type_id)
            return out, None
        updates.append("updated_at = NOW()")
        params.append(type_id)
        await db.execute(
            f"UPDATE event_types SET {', '.join(updates)} WHERE id = ${pos}",
            tuple(params),
        )
        row = await db.execute(
            """SELECT id, key, display_name, description, required_params, validation_type,
                      report_alert_config, status, requires_show_event_type_id, is_critical,
                      created_at, updated_at
               FROM event_types WHERE id = $1""",
            (type_id,),
        )
        out = serialize_json(row) if row else await get_event_type_by_id(type_id)
        return out, None


async def archive_event_type(type_id: str) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute("SELECT id FROM event_types WHERE id = $1", (type_id,))
        if not row:
            return None
        await db.execute(
            "UPDATE event_types SET status = 'archived', updated_at = NOW() WHERE id = $1",
            (type_id,),
        )
        row = await db.execute(
            """SELECT id, key, display_name, description, required_params, validation_type,
                      report_alert_config, status, requires_show_event_type_id, is_critical,
                      created_at, updated_at
               FROM event_types WHERE id = $1""",
            (type_id,),
        )
        return serialize_json(row) if row else None
