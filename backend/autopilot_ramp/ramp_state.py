import json

from autopilot_ramp.ramp_apply import apply_ramp_step_to_experiment
from autopilot_ramp.types import DECISION_ACTIONS, RAMP_MODES
from core import serialize_json
from database.database import Database


async def get_ramp_state(experiment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT experiment_id, ramp_plan_id, current_step_index, mode,
                      started_at, last_eval_at, manual_override_by_user_id, manual_override_at, updated_at
               FROM experiment_ramp_state WHERE experiment_id = $1""",
            (experiment_id,),
        )
        return serialize_json(row)


async def start_autopilot(experiment_id: str) -> tuple[dict | None, str | None]:
    async with Database() as db:
        plan = await db.execute(
            "SELECT id FROM ramp_plans WHERE experiment_id = $1", (experiment_id,)
        )
        if not plan:
            return None, "ramp_plan_not_found"
        ex = await db.execute("SELECT id, status FROM experiments WHERE id = $1", (experiment_id,))
        if not ex or ex["status"] != "running":
            return None, "experiment_not_running"

        existing = await db.execute(
            "SELECT 1 FROM experiment_ramp_state WHERE experiment_id = $1", (experiment_id,)
        )
        if existing:
            return None, "already_started"

        await db.execute(
            """INSERT INTO experiment_ramp_state (experiment_id, ramp_plan_id, current_step_index, mode)
               VALUES ($1, $2, 0, 'autopilot')""",
            (experiment_id, plan["id"]),
        )
        await _log_decision(
            db, experiment_id, "start", 0, 0, {"message": "autopilot started"}, "autopilot", None
        )
    await apply_ramp_step_to_experiment(experiment_id)
    return await get_ramp_state(experiment_id), None


async def set_ramp_mode(
    experiment_id: str, mode: str, user_id: str | None = None
) -> tuple[dict | None, str | None]:
    if mode not in RAMP_MODES:
        return None, "invalid_mode"
    async with Database() as db:
        state = await db.execute(
            "SELECT current_step_index FROM experiment_ramp_state WHERE experiment_id = $1",
            (experiment_id,),
        )
        if not state:
            return None, "ramp_not_started"

        await db.execute(
            """UPDATE experiment_ramp_state SET
                   mode = $1::varchar,
                   manual_override_by_user_id = $2,
                   manual_override_at = CASE WHEN $1::varchar IN ('manual', 'paused') THEN NOW() ELSE NULL END,
                   updated_at = NOW()
               WHERE experiment_id = $3""",
            (mode, user_id, experiment_id),
        )
        action = "resume" if mode == "autopilot" else "pause"
        await _log_decision(
            db,
            experiment_id,
            action,
            state["current_step_index"],
            state["current_step_index"],
            {"mode": mode, "user_id": user_id},
            "manual",
            user_id,
        )
    return await get_ramp_state(experiment_id), None


async def override_step(
    experiment_id: str, to_step_index: int, user_id: str
) -> tuple[dict | None, str | None]:
    async with Database() as db:
        state = await db.execute(
            """SELECT current_step_index, ramp_plan_id, mode
               FROM experiment_ramp_state WHERE experiment_id = $1""",
            (experiment_id,),
        )
        if not state:
            return None, "ramp_not_started"
        if state.get("mode") != "manual":
            return None, "override_only_in_manual_mode"
        from_idx = state["current_step_index"]
        steps = await db.execute_all(
            "SELECT step_index FROM ramp_steps WHERE ramp_plan_id = $1 ORDER BY step_index",
            (state["ramp_plan_id"],),
        )
        max_idx = max(s["step_index"] for s in steps) if steps else 0
        if to_step_index < 0 or to_step_index > max_idx:
            return None, "invalid_step_index"

        await db.execute(
            """UPDATE experiment_ramp_state SET
                   current_step_index = $1,
                   last_eval_at = NOW(),
                   manual_override_by_user_id = $2,
                   manual_override_at = NOW(),
                   updated_at = NOW()
               WHERE experiment_id = $3""",
            (to_step_index, user_id, experiment_id),
        )
        await _log_decision(
            db,
            experiment_id,
            "override",
            from_idx,
            to_step_index,
            {"user_id": user_id, "reason": "manual override"},
            "manual",
            user_id,
        )
    await apply_ramp_step_to_experiment(experiment_id)
    return await get_ramp_state(experiment_id), None


async def log_autopilot_decision(
    experiment_id: str,
    action: str,
    from_step_index: int,
    to_step_index: int | None,
    reason: dict,
) -> None:
    if action not in DECISION_ACTIONS:
        return
    async with Database() as db:
        await _log_decision(
            db, experiment_id, action, from_step_index, to_step_index, reason, "autopilot", None
        )


async def _log_decision(
    db,
    experiment_id: str,
    action: str,
    from_step_index: int,
    to_step_index: int | None,
    reason: dict,
    triggered_by: str,
    user_id: str | None,
) -> None:
    await db.execute(
        """INSERT INTO experiment_ramp_decision_log
           (experiment_id, action, from_step_index, to_step_index, reason, triggered_by, user_id)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)""",
        (
            experiment_id,
            action,
            from_step_index,
            to_step_index,
            json.dumps(reason),
            triggered_by,
            user_id,
        ),
    )


async def get_ramp_decision_log(experiment_id: str, limit: int = 100) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT id, experiment_id, decided_at, action, from_step_index, to_step_index,
                      reason, triggered_by, user_id, created_at
               FROM experiment_ramp_decision_log
               WHERE experiment_id = $1 ORDER BY decided_at DESC LIMIT $2""",
            (experiment_id, limit),
        )
        return serialize_json(rows)
