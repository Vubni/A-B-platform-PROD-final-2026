import uuid
from datetime import UTC, datetime, timedelta

from core import serialize_json
from database.database import Database
from functions.experiments import (
    pause_experiment,
    record_guardrail_trigger,
    rollback_experiment_to_control,
)
from functions.metrics import get_metric_by_key
from functions.reports import _compute_metric_value, _decision_ids_by_variant


async def list_metric_guardrails() -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT metric_key,
                      threshold,
                      window_seconds,
                      action,
                      created_at,
                      updated_at
               FROM metric_guardrails
               ORDER BY metric_key"""
        )
        return serialize_json(rows)


async def get_metric_guardrail(metric_key: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT metric_key,
                      threshold,
                      window_seconds,
                      action,
                      created_at,
                      updated_at
               FROM metric_guardrails
               WHERE metric_key = $1""",
            (metric_key.strip(),),
        )
        return serialize_json(row)


async def upsert_metric_guardrail(
    metric_key: str, threshold: float, window_seconds: int, action: str
) -> dict | None:
    async with Database() as db:
        metric_row = await db.execute(
            "SELECT key FROM metric_catalog WHERE key = $1", (metric_key.strip(),)
        )
        if not metric_row:
            return None

        await db.execute(
            """INSERT INTO metric_guardrails (metric_key, threshold, window_seconds, action)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (metric_key)
               DO UPDATE SET
                   threshold = EXCLUDED.threshold,
                   window_seconds = EXCLUDED.window_seconds,
                   action = EXCLUDED.action,
                   updated_at = NOW()""",
            (metric_key.strip(), threshold, window_seconds, action),
        )
        row = await db.execute(
            """SELECT metric_key,
                      threshold,
                      window_seconds,
                      action,
                      created_at,
                      updated_at
               FROM metric_guardrails
               WHERE metric_key = $1""",
            (metric_key.strip(),),
        )
        return serialize_json(row)


async def delete_metric_guardrail(metric_key: str) -> bool:
    async with Database() as db:
        existing = await db.execute(
            "SELECT 1 FROM metric_guardrails WHERE metric_key = $1", (metric_key.strip(),)
        )
        if not existing:
            return False
        await db.execute(
            "DELETE FROM metric_guardrails WHERE metric_key = $1", (metric_key.strip(),)
        )
        return True


async def _evaluate_experiment_guardrails(experiment_id: str) -> None:
    now = datetime.now(UTC)

    async with Database() as db:
        experiment = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not experiment or experiment.get("status") != "running":
            return

        guardrails = await db.execute_all(
            """SELECT em.metric_key,
                      mg.threshold,
                      mg.window_seconds,
                      mg.action
               FROM experiment_metrics em
               JOIN metric_guardrails mg ON mg.metric_key = em.metric_key
               WHERE em.experiment_id = $1 AND em.metric_type = 'guardrail'""",
            (experiment_id,),
        )
        if not guardrails:
            return

        variant_rows = await db.execute_all(
            "SELECT id FROM experiment_variants WHERE experiment_id = $1", (experiment_id,)
        )
        all_decision_ids = []
        for v in variant_rows or []:
            dids = await _decision_ids_by_variant(db, experiment_id, v["id"])
            all_decision_ids.extend(dids)

        if not all_decision_ids:
            return

        for gr in guardrails or []:
            metric_key = gr.get("metric_key")
            threshold = gr.get("threshold")
            window_seconds = gr.get("window_seconds")
            action = gr.get("action")

            if not metric_key or threshold is None or not window_seconds:
                continue

            metric_catalog_row = await get_metric_by_key(metric_key)
            if not metric_catalog_row:
                continue

            start_ts = now - timedelta(seconds=int(window_seconds))
            value = await _compute_metric_value(
                db, all_decision_ids, start_ts, now, metric_catalog_row
            )
            if value is None:
                continue

            if float(value) > float(threshold):
                details = {
                    "reason": "guardrail_threshold_exceeded",
                    "threshold": float(threshold),
                    "window_seconds": int(window_seconds),
                    "action": action,
                    "metric_value": float(value),
                }
                await record_guardrail_trigger(
                    experiment_id=str(experiment_id),
                    metric_key=str(metric_key),
                    threshold=float(threshold),
                    window_seconds=int(window_seconds),
                    action=str(action) if action is not None else None,
                    metric_value=float(value),
                    details=details,
                )

                if action == "pause":
                    await pause_experiment(str(experiment_id))
                elif action == "rollback_to_control":
                    await rollback_experiment_to_control(str(experiment_id))


async def check_guardrails_for_decisions(decision_ids: list[str]) -> None:
    if not decision_ids:
        return
    try:
        decision_ids_uuid = [
            uuid.UUID(d) if isinstance(d, str) else d for d in decision_ids if d
        ]
    except (ValueError, TypeError):
        return
    if not decision_ids_uuid:
        return

    async with Database() as db:
        rows = await db.execute_all(
            """SELECT DISTINCT experiment_id
               FROM decisions
               WHERE decision_id = ANY($1::uuid[])
                 AND experiment_id IS NOT NULL""",
            (decision_ids_uuid,),
        )

    experiment_ids = [str(r["experiment_id"]) for r in (rows or []) if r.get("experiment_id")]
    for exp_id in experiment_ids:
        await _evaluate_experiment_guardrails(exp_id)
