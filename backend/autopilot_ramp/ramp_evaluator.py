import os
from datetime import UTC, datetime, timedelta

from autopilot_ramp.ramp_apply import apply_ramp_step_to_experiment
from autopilot_ramp.ramp_plan import get_ramp_plan_by_experiment_id
from autopilot_ramp.ramp_state import log_autopilot_decision
from database.database import Database
from functions.experiments import pause_experiment, rollback_experiment_to_control

EVAL_INTERVAL_SECONDS = int(os.getenv("AUTOPILOT_EVAL_INTERVAL_SECONDS", "60"))


async def sync_and_tick_autopilot(experiment_id: str) -> None:
    await apply_ramp_step_to_experiment(experiment_id)
    await evaluate_autopilot_tick(experiment_id)


async def evaluate_autopilot_tick(experiment_id: str) -> None:
    async with Database() as db:
        state = await db.execute(
            """SELECT ramp_plan_id, current_step_index, mode, last_eval_at
               FROM experiment_ramp_state WHERE experiment_id = $1""",
            (experiment_id,),
        )
        if not state or state["mode"] != "autopilot":
            return
        ex = await db.execute("SELECT id, status FROM experiments WHERE id = $1", (experiment_id,))
        if not ex or ex["status"] != "running":
            return

        now = datetime.now(UTC)
        last_eval = state.get("last_eval_at")
        if last_eval:
            if isinstance(last_eval, str):
                try:
                    last_eval = datetime.fromisoformat(last_eval.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    last_eval = None
            if last_eval and (now - last_eval).total_seconds() < EVAL_INTERVAL_SECONDS:
                return

        plan = await get_ramp_plan_by_experiment_id(experiment_id)
        if not plan:
            return

        window_sec = int(plan.get("observation_window_seconds") or 300)
        since = now - timedelta(seconds=window_sec)
        current_step = int(state.get("current_step_index") or 0)
        steps = sorted(plan.get("steps") or [], key=lambda s: s.get("step_index", 0))

        await db.execute(
            "UPDATE experiment_ramp_state SET last_eval_at = $1, updated_at = NOW() WHERE experiment_id = $2",
            (now, experiment_id),
        )

    safety_action = await _check_safety(experiment_id, plan, since, now)
    if safety_action:
        await _apply_safety_action(experiment_id, plan, current_step, safety_action)
        return

    can_step_up, reason = await _check_gates(experiment_id, plan, current_step, steps, since, now)
    if can_step_up and (current_step + 1) < len(steps):
        await _do_step_up(experiment_id, current_step, current_step + 1, steps, reason)
    elif not can_step_up and reason:
        await log_autopilot_decision(
            experiment_id, "no_change", current_step, current_step, reason
        )


async def _check_safety(
    experiment_id: str, plan: dict, since: datetime, now: datetime
) -> dict | None:
    async with Database() as db:
        triggered = await db.execute_all(
            """SELECT metric_key, action, triggered_at FROM experiment_guardrail_history
               WHERE experiment_id = $1 AND triggered_at >= $2 AND triggered_at <= $3""",
            (experiment_id, since, now),
        )
    if not triggered:
        return None
    actions = {sa["trigger_type"]: sa for sa in plan.get("safety_actions") or []}
    for row in triggered:
        action_cfg = actions.get("guardrail_triggered")
        if action_cfg:
            return {
                "trigger_type": "guardrail_triggered",
                "action": action_cfg.get("action"),
                "metric_key": row.get("metric_key"),
            }
    return None


async def _apply_safety_action(
    experiment_id: str, plan: dict, current_step: int, safety: dict
) -> None:
    action = (safety or {}).get("action")
    trigger_type = (safety or {}).get("trigger_type")

    if action == "pause":
        await pause_experiment(experiment_id)
        await log_autopilot_decision(
            experiment_id,
            "pause",
            current_step,
            None,
            {
                "reason": "safety",
                "trigger_type": trigger_type,
                "metric_key": safety.get("metric_key"),
            },
        )
    elif action == "rollback_to_control":
        await rollback_experiment_to_control(experiment_id)
        await log_autopilot_decision(
            experiment_id,
            "rollback",
            current_step,
            None,
            {"reason": "safety", "trigger_type": trigger_type},
        )
    elif action == "step_back":
        if current_step > 0:
            new_step = current_step - 1
            async with Database() as db:
                await db.execute(
                    """UPDATE experiment_ramp_state SET current_step_index = $1, step_entered_at = NOW(), updated_at = NOW()
                       WHERE experiment_id = $2""",
                    (new_step, experiment_id),
                )
            await apply_ramp_step_to_experiment(experiment_id)
            await log_autopilot_decision(
                experiment_id,
                "step_back",
                current_step,
                new_step,
                {"reason": "safety", "trigger_type": trigger_type},
            )


async def _check_gates(
    experiment_id: str, plan: dict, current_step: int, steps: list, since: datetime, now: datetime
) -> tuple[bool, dict]:
    gates = plan.get("gate_data_sufficiency") or {}
    min_total = int(gates.get("min_total_impressions") or 0)
    min_per_variant = int(gates.get("min_impressions_per_variant") or 0)
    min_minutes = int(gates.get("min_minutes_on_step") or 0)

    async with Database() as db:
        state = await db.execute(
            "SELECT started_at, step_entered_at, last_eval_at FROM experiment_ramp_state WHERE experiment_id = $1",
            (experiment_id,),
        )
        step_start = (state.get("step_entered_at") or state.get("started_at")) if state else None
        if step_start and isinstance(step_start, str):
            try:
                step_start = datetime.fromisoformat(step_start.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                step_start = None
        minutes_on_step = (now - step_start).total_seconds() / 60.0 if step_start else 0

        counts = await db.execute(
            """SELECT COUNT(*) AS total
               FROM decisions
               WHERE experiment_id = $1 AND created_at >= $2 AND created_at <= $3""",
            (experiment_id, since, now),
        )
        total = int((counts or {}).get("total") or 0)

        variant_counts = await db.execute_all(
            """SELECT variant_id, COUNT(*) AS cnt
               FROM decisions
               WHERE experiment_id = $1 AND variant_id IS NOT NULL AND created_at >= $2 AND created_at <= $3
               GROUP BY variant_id""",
            (experiment_id, since, now),
        )
        min_variant_count = min((r["cnt"] for r in (variant_counts or [])), default=0)

    reason = {}
    if min_total > 0 and total < min_total:
        reason["gate"] = "data_sufficiency"
        reason["min_total_impressions"] = min_total
        reason["actual_total"] = total
        return False, reason
    if min_per_variant > 0 and min_variant_count < min_per_variant:
        reason["gate"] = "data_sufficiency"
        reason["min_impressions_per_variant"] = min_per_variant
        reason["actual_min_per_variant"] = min_variant_count
        return False, reason
    if min_minutes > 0 and minutes_on_step < min_minutes:
        reason["gate"] = "data_sufficiency"
        reason["min_minutes_on_step"] = min_minutes
        reason["actual_minutes"] = round(minutes_on_step, 1)
        return False, reason
    return True, reason


async def _do_step_up(
    experiment_id: str, from_idx: int, to_idx: int, steps: list, reason: dict
) -> None:
    async with Database() as db:
        await db.execute(
            """UPDATE experiment_ramp_state SET current_step_index = $1, step_entered_at = NOW(), updated_at = NOW()
               WHERE experiment_id = $2""",
            (to_idx, experiment_id),
        )
    await apply_ramp_step_to_experiment(experiment_id)
    await log_autopilot_decision(
        experiment_id, "step_up", from_idx, to_idx, {"reason": "gates_passed", **reason}
    )
