import uuid
from typing import Any

from core import serialize_json
from database.database import Database

FLAG_VALUE_TYPES = ("string", "number", "bool")


def validate_flag_value_by_type(
    value_type: str, raw_value: str, field_name: str = "value"
) -> None:
    if value_type == "string":
        return
    if value_type == "number":
        try:
            if "." in raw_value:
                float(raw_value)
            else:
                int(raw_value)
        except ValueError as err:
            raise ValueError(f"{field_name} must be a valid number for value_type=number") from err
        return
    if value_type == "bool":
        if raw_value.lower() not in ("true", "false", "1", "0", "yes", "no"):
            raise ValueError(
                f"{field_name} for value_type=bool must be one of: true, false, 1, 0, yes, no"
            )
        return
    raise ValueError(f"value_type must be one of {FLAG_VALUE_TYPES}")


def cast_flag_value(value_type: str, raw_value: str) -> Any:
    if value_type == "string":
        return raw_value
    if value_type == "number":
        try:
            if "." in raw_value:
                return float(raw_value)
            return int(raw_value)
        except ValueError:
            return raw_value
    if value_type == "bool":
        return raw_value.lower() in ("true", "1", "yes")
    return raw_value


async def get_flag_by_key(key: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT id, key, value_type::text, default_value, description, owner, metadata, created_at, updated_at
               FROM feature_flags WHERE key = $1""",
            (key,),
        )
        if not row:
            return None
        return serialize_json(row)


async def get_flag_by_id(flag_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT id, key, value_type::text, default_value, description, owner, metadata, created_at, updated_at
               FROM feature_flags WHERE id = $1""",
            (flag_id,),
        )
        if not row:
            return None
        return serialize_json(row)


async def get_flags_list() -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT id, key, value_type::text, default_value, description, owner, metadata, created_at, updated_at
               FROM feature_flags ORDER BY key"""
        )
        return [serialize_json(r) for r in (rows or [])]


async def create_flag(
    key: str,
    value_type: str,
    default_value: str,
    description: str | None = None,
    owner: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    async with Database() as db:
        existing = await db.execute("SELECT id FROM feature_flags WHERE key = $1", (key,))
        if existing:
            return None
        await db.execute(
            """INSERT INTO feature_flags (key, value_type, default_value, description, owner, metadata)
               VALUES ($1, $2::flag_value_type, $3, $4, $5, $6)""",
            (key, value_type, default_value, description, owner, metadata),
        )
        row = await db.execute(
            """SELECT id, key, value_type::text, default_value, description, owner, metadata, created_at, updated_at
               FROM feature_flags WHERE key = $1""",
            (key,),
        )
        return serialize_json(row)


async def update_flag_default_value(key: str, default_value: str) -> dict | None:
    async with Database() as db:
        exists = await db.execute("SELECT id FROM feature_flags WHERE key = $1", (key,))
        if not exists:
            return None
        await db.execute(
            """UPDATE feature_flags SET default_value = $1, updated_at = NOW() WHERE key = $2""",
            (default_value, key),
        )
        row = await db.execute(
            """SELECT id, key, value_type::text, default_value, description, owner, metadata, created_at, updated_at
               FROM feature_flags WHERE key = $1""",
            (key,),
        )
        return serialize_json(row)


async def resolve_flag_value(
    flag_key: str, subject_id: str, attributes: dict | None = None
) -> dict | None:
    flag = await get_flag_by_key(flag_key)
    if not flag:
        return None

    value_type = flag.get("value_type") or "string"
    default_value_raw = flag.get("default_value") or ""
    effective_value = cast_flag_value(value_type, str(default_value_raw))
    decision_id = str(uuid.uuid4())

    experiment_id = None
    variant = None
    default_used = True

    return {
        "value": effective_value,
        "decision_id": decision_id,
        "experiment_id": experiment_id,
        "variant": variant,
        "default_used": default_used,
    }
