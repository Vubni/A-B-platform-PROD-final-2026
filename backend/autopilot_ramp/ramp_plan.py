import json

from autopilot_ramp.types import (
    SAFETY_ACTIONS,
    SAFETY_TRIGGER_TYPES,
    gate_data_health_defaults,
    gate_data_sufficiency_defaults,
    gate_safety_defaults,
)
from core import serialize_json
from database.database import Database


async def get_ramp_plan_by_experiment_id(experiment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT id, experiment_id, observation_window_seconds,
                      gate_data_sufficiency, gate_safety, gate_data_health,
                      created_at, updated_at
               FROM ramp_plans WHERE experiment_id = $1""",
            (experiment_id,))
        if not row:
            return None
        plan = serialize_json(row)
        plan["steps"] = await _get_steps_for_plan(db, str(plan["id"]))
        plan["safety_actions"] = await _get_safety_actions_for_plan(db, str(plan["id"]))
        return plan


async def _get_steps_for_plan(db, ramp_plan_id: str) -> list:
    rows = await db.execute_all(
        """SELECT step_index, traffic_fraction
           FROM ramp_steps WHERE ramp_plan_id = $1 ORDER BY step_index""",
        (ramp_plan_id,))
    return serialize_json(rows)


async def _get_safety_actions_for_plan(db, ramp_plan_id: str) -> list:
    rows = await db.execute_all(
        """SELECT trigger_type, action, notify
           FROM ramp_safety_actions WHERE ramp_plan_id = $1""",
        (ramp_plan_id,))
    return serialize_json(rows)


async def create_or_update_ramp_plan(experiment_id: str, observation_window_seconds: int, steps: list[dict],
    gate_data_sufficiency: dict | None = None, gate_safety: dict | None = None, gate_data_health: dict | None = None,
    safety_actions: list[dict] | None = None) -> tuple[dict | None, str | None]:
    if observation_window_seconds <= 0:
        return None, "invalid_observation_window"
    if not steps or not all(
        isinstance(s.get("traffic_fraction"), (int, float)) and 0 < s.get("traffic_fraction", 0) <= 1
        for s in steps
    ):
        return None, "invalid_steps"

    gate_data_sufficiency = gate_data_sufficiency or gate_data_sufficiency_defaults()
    gate_safety = gate_safety or gate_safety_defaults()
    gate_data_health = gate_data_health or gate_data_health_defaults()
    safety_actions = safety_actions or []

    for sa in safety_actions:
        if sa.get("trigger_type") not in SAFETY_TRIGGER_TYPES:
            return None, "invalid_trigger_type"
        if sa.get("action") not in SAFETY_ACTIONS:
            return None, "invalid_safety_action"

    async with Database() as db:
        ex = await db.execute(
            "SELECT id FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not ex:
            return None, "experiment_not_found"
        existing = await db.execute(
            "SELECT id FROM ramp_plans WHERE experiment_id = $1", (experiment_id,)
        )
        plan_id = str(existing["id"]) if existing else None

        if plan_id:
            await db.execute(
                """UPDATE ramp_plans SET
                   observation_window_seconds = $1,
                   gate_data_sufficiency = $2::jsonb,
                   gate_safety = $3::jsonb,
                   gate_data_health = $4::jsonb,
                   updated_at = NOW()
                   WHERE id = $5""",
                (
                    observation_window_seconds,
                    json.dumps(gate_data_sufficiency),
                    json.dumps(gate_safety),
                    json.dumps(gate_data_health),
                    plan_id,
                ),
            )
            await db.execute(
                "DELETE FROM ramp_steps WHERE ramp_plan_id = $1", (plan_id,)
            )
            await db.execute(
                "DELETE FROM ramp_safety_actions WHERE ramp_plan_id = $1", (plan_id,)
            )
        else:
            plan_id = await db.fetchval(
                """INSERT INTO ramp_plans (
                       experiment_id, observation_window_seconds,
                       gate_data_sufficiency, gate_safety, gate_data_health
                   ) VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb) RETURNING id""",
                (
                    experiment_id,
                    observation_window_seconds,
                    json.dumps(gate_data_sufficiency),
                    json.dumps(gate_safety),
                    json.dumps(gate_data_health),
                ),
            )
            plan_id = str(plan_id)

        for idx, s in enumerate(steps):
            step_index = s.get("step_index", idx)
            traffic_fraction = float(s["traffic_fraction"])
            await db.execute(
                """INSERT INTO ramp_steps (ramp_plan_id, step_index, traffic_fraction)
                   VALUES ($1, $2, $3)""",
                (plan_id, step_index, traffic_fraction),
            )

        for sa in safety_actions:
            await db.execute(
                """INSERT INTO ramp_safety_actions (ramp_plan_id, trigger_type, action, notify)
                   VALUES ($1, $2, $3, $4)""",
                (
                    plan_id,
                    sa["trigger_type"],
                    sa["action"],
                    sa.get("notify", True),
                ),
            )

    return await get_ramp_plan_by_experiment_id(experiment_id), None


async def delete_ramp_plan(experiment_id: str) -> bool:
    """Удалить план раскатки по experiment_id."""
    async with Database() as db:
        row = await db.execute(
            "SELECT id FROM ramp_plans WHERE experiment_id = $1",
            (experiment_id,),
        )
        if not row:
            return False
        await db.execute(
            "DELETE FROM ramp_plans WHERE experiment_id = $1",
            (experiment_id,),
        )
        return True
