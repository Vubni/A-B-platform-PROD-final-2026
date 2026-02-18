import json
from typing import Any, Optional

from core import serialize_json
from database.database import Database


async def list_metrics() -> list[dict[str, Any]]:
    async with Database() as db:
        rows = await db.execute_all(
            "SELECT id, key, name, description, aggregation_rule, attribution_rule, event_expectations, unit, created_at, updated_at \
               FROM metric_catalog ORDER BY key")
        return serialize_json(rows)


async def get_metric_by_key(key: str) -> Optional[dict[str, Any]]:
    if not key or not str(key).strip():
        return None
    key = str(key).strip()
    async with Database() as db:
        row = await db.execute(
            "SELECT id, key, name, description, aggregation_rule, attribution_rule, event_expectations, unit, created_at, updated_at \
               FROM metric_catalog WHERE key = $1",
            (key,))
        return serialize_json(row) if row else None


async def create_metric(key: str, name: str, aggregation_rule: dict, description: Optional[str] = None,
    attribution_rule: Optional[dict] = None, event_expectations: Optional[dict] = None, unit: Optional[str] = None) -> tuple[Optional[dict], Optional[str]]:
    if not key or not str(key).strip():
        return None, "invalid_key"
    key = str(key).strip()
    if not name or not str(name).strip():
        return None, "invalid_name"
    name = str(name).strip()
    if not aggregation_rule or not isinstance(aggregation_rule, dict):
        return None, "invalid_aggregation_rule"

    async with Database() as db:
        existing = await db.execute("SELECT 1 FROM metric_catalog WHERE key = $1", (key,))
        if existing:
            return None, "duplicate_key"
        await db.execute(
            "INSERT INTO metric_catalog (key, name, description, aggregation_rule, attribution_rule, event_expectations, unit) \
               VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7)",
            (
                key,
                name,
                description or None,
                json.dumps(aggregation_rule),
                json.dumps(attribution_rule) if attribution_rule is not None else None,
                json.dumps(event_expectations) if event_expectations is not None else None,
                unit))
    created = await get_metric_by_key(key)
    return (created, None) if created else (None, "db_error")


async def update_metric(key: str, name: Optional[str] = None, description: Optional[str] = None,
    aggregation_rule: Optional[dict] = None, attribution_rule: Optional[dict] = None,
    event_expectations: Optional[dict] = None, unit: Optional[str] = None,) -> tuple[Optional[dict], Optional[str]]:
    if not key or not str(key).strip():
        return None, "not_found"
    key = str(key).strip()

    updates = ["updated_at = NOW()"]
    params: list[Any] = []
    idx = 1
    if name is not None:
        updates.append(f"name = ${idx}")
        params.append(name.strip() if isinstance(name, str) else name)
        idx += 1
    if description is not None:
        updates.append(f"description = ${idx}")
        params.append(description if description else None)
        idx += 1
    if aggregation_rule is not None:
        updates.append(f"aggregation_rule = ${idx}::jsonb")
        params.append(json.dumps(aggregation_rule))
        idx += 1
    if attribution_rule is not None:
        updates.append(f"attribution_rule = ${idx}::jsonb")
        params.append(json.dumps(attribution_rule) if attribution_rule else None)
        idx += 1
    if event_expectations is not None:
        updates.append(f"event_expectations = ${idx}::jsonb")
        params.append(json.dumps(event_expectations) if event_expectations else None)
        idx += 1
    if unit is not None:
        updates.append(f"unit = ${idx}")
        params.append(unit)
        idx += 1

    if len(params) == 0:
        return await get_metric_by_key(key), None

    params.append(key)
    async with Database() as db:
        await db.execute(
            f"UPDATE metric_catalog SET {', '.join(updates)} WHERE key = ${idx}",
            tuple(params))
    updated = await get_metric_by_key(key)
    return (updated, None) if updated else (None, "not_found")
