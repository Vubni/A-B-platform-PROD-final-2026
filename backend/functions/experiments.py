import json
from decimal import Decimal

import asyncpg

from core import serialize_json
from database.database import Database

EXPERIMENT_STATUSES = (
    "draft",
    "on_review",
    "approved",
    "running",
    "paused",
    "completed",
    "archived",
    "rejected",
)
METRIC_TYPES = ("primary", "auxiliary", "guardrail")
REVIEW_ACTIONS = ("approved", "requested_changes", "rejected")


def _validate_metrics_shape(metrics: list[dict]) -> str | None:
    if not metrics:
        return None
    primary_count = sum(1 for m in metrics if (m.get("metric_type") or "").strip() == "primary")
    if primary_count != 1:
        return "Должна быть ровно одна метрика с metric_type 'primary'"
    for m in metrics:
        key = (m.get("metric_key") or "").strip()
        if not key or len(key) > 255:
            return "metric_key обязателен и не более 255 символов"
        if (m.get("metric_type") or "").strip() not in METRIC_TYPES:
            return f"metric_type должен быть один из: {METRIC_TYPES}"
    return None


async def _get_missing_metric_keys(db, keys: list[str]) -> list[str]:
    if not keys:
        return []
    unique = list(dict.fromkeys(k for k in keys if k))
    rows = await db.execute_all(
        "SELECT key FROM metric_catalog WHERE key = ANY($1::text[])",
        (unique,),
    )
    found = {r["key"] for r in (rows or [])}
    return [k for k in unique if k not in found]


async def create_experiment(
    flag_id: str,
    name: str,
    audience_fraction: float,
    created_by: str | None = None,
    targeting_rule: str | None = None,
    metrics: list[dict] | None = None,
) -> tuple[dict | None, str | None, list[str] | None]:
    if metrics is not None:
        err = _validate_metrics_shape(metrics)
        if err:
            return (None, "metrics_validation", [err])
    async with Database() as db:
        flag_row = await db.execute("SELECT 1 FROM feature_flags WHERE id = $1", (flag_id,))
        if not flag_row:
            return (None, "flag_not_found", None)
        new_id = await db.fetchval(
            """INSERT INTO experiments (flag_id, name, audience_fraction, targeting_rule, created_by)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            (flag_id, name, audience_fraction, targeting_rule, created_by),
        )
        if not new_id:
            return (None, "flag_not_found", None)

        if metrics:
            metric_keys = [m.get("metric_key", "").strip() for m in metrics]
            missing = await _get_missing_metric_keys(db, metric_keys)
            if missing:
                return (None, "metrics_not_in_catalog", missing)
            for m in metrics:
                await db.execute(
                    """INSERT INTO experiment_metrics (experiment_id, metric_key, metric_type)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (experiment_id, metric_key, metric_type) DO NOTHING""",
                    (
                        new_id,
                        m.get("metric_key", "").strip(),
                        (m.get("metric_type") or "").strip(),
                    ),
                )
    return (await get_experiment_by_id(str(new_id)), None, None)


async def _get_experiment_row_using_db(db, experiment_id: str):
    try:
        row = await db.execute(
            """SELECT e.id, e.flag_id, e.name, e.status::text, e.version,
                      e.audience_fraction, e.targeting_rule,
                      e.created_by, e.created_at, e.updated_at,
                      e.completion_outcome, e.completion_comment, e.completion_winner_variant_id,
                      f.key AS flag_key
               FROM experiments e
               JOIN feature_flags f ON f.id = e.flag_id
               WHERE e.id = $1""",
            (experiment_id,),
        )
    except asyncpg.exceptions.UndefinedColumnError:
        row = await db.execute(
            """SELECT e.id, e.flag_id, e.name, e.status::text, e.version,
                      e.audience_fraction, e.targeting_rule,
                      e.created_by, e.created_at, e.updated_at,
                      f.key AS flag_key
               FROM experiments e
               JOIN feature_flags f ON f.id = e.flag_id
               WHERE e.id = $1""",
            (experiment_id,),
        )
        if row:
            row["completion_outcome"] = None
            row["completion_comment"] = None
            row["completion_winner_variant_id"] = None
    if not row:
        return None
    row["variants"] = await db.execute_all(
        """SELECT id, experiment_id, variant_name, variant_value, weight, is_control, created_at
           FROM experiment_variants WHERE experiment_id = $1 ORDER BY variant_name""",
        (experiment_id,),
    )
    row["metrics"] = await db.execute_all(
        """SELECT id, experiment_id, metric_key, metric_type, created_at
           FROM experiment_metrics WHERE experiment_id = $1""",
        (experiment_id,),
    )
    return serialize_json(row)


async def get_experiment_by_id(experiment_id: str) -> dict | None:
    async with Database() as db:
        return await _get_experiment_row_using_db(db, experiment_id)


async def get_experiments_list(
    flag_id: str | None = None, status: str | None = None
) -> list[dict]:
    async with Database() as db:
        sql = """SELECT e.id, e.flag_id, e.name, e.status::text, e.version,
                        e.audience_fraction, e.targeting_rule,
                        e.created_by, e.created_at, e.updated_at,
                        f.key AS flag_key
                 FROM experiments e
                 JOIN feature_flags f ON f.id = e.flag_id
                 WHERE 1=1"""
        params = []
        idx = 1
        if flag_id:
            sql += f" AND e.flag_id = ${idx}"
            params.append(flag_id)
            idx += 1
        if status:
            sql += f" AND e.status::text = ${idx}"
            params.append(status)
            idx += 1
        sql += " ORDER BY e.updated_at DESC"
        rows = await db.execute_all(sql, tuple(params))
        return serialize_json(rows)


async def update_experiment(
    experiment_id: str,
    name: str | None = None,
    audience_fraction: float | None = None,
    targeting_rule: str | None = None,
    metrics: list[dict] | None = None,
) -> tuple[dict | None, str | None, list[str] | None]:
    if metrics is not None:
        err = _validate_metrics_shape(metrics)
        if err:
            return (None, "metrics_validation", [err])
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status, version FROM experiments WHERE id = $1",
            (experiment_id,),
        )
        if not row:
            return (None, "experiment_not_found", None)
        is_draft = row.get("status") == "draft"
        if not is_draft and (
            audience_fraction is not None or targeting_rule is not None or metrics is not None
        ):
            return (None, "experiment_not_found", None)
        updates = ["updated_at = NOW()"]
        params = []
        idx = 1
        if name is not None:
            updates.append(f"name = ${idx}")
            params.append(name)
            idx += 1
        if audience_fraction is not None:
            updates.append(f"audience_fraction = ${idx}")
            params.append(audience_fraction)
            idx += 1
        if targeting_rule is not None:
            updates.append(f"targeting_rule = ${idx}")
            params.append(targeting_rule)
            idx += 1
        if len(params) == 0 and metrics is None:
            return (await get_experiment_by_id(experiment_id), None, None)
        new_version = (row.get("version") or 1) + 1
        updates.append(f"version = ${idx}")
        params.append(new_version)
        idx += 1
        params.append(experiment_id)
        await db.execute(
            f"UPDATE experiments SET {', '.join(updates)} WHERE id = ${idx}",
            tuple(params),
        )

        if metrics is not None:
            metric_keys = [m.get("metric_key", "").strip() for m in metrics]
            missing = await _get_missing_metric_keys(db, metric_keys)
            if missing:
                return (None, "metrics_not_in_catalog", missing)
            await db.execute(
                "DELETE FROM experiment_metrics WHERE experiment_id = $1",
                (experiment_id,),
            )
            for m in metrics:
                await db.execute(
                    """INSERT INTO experiment_metrics (experiment_id, metric_key, metric_type)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (experiment_id, metric_key, metric_type) DO NOTHING""",
                    (
                        experiment_id,
                        m.get("metric_key", "").strip(),
                        (m.get("metric_type") or "").strip(),
                    ),
                )
        snapshot = await _build_experiment_snapshot(db, experiment_id)
        if snapshot:
            await db.execute(
                """INSERT INTO experiment_version_snapshots (experiment_id, version, snapshot)
                   VALUES ($1, $2, $3)""",
                (experiment_id, new_version, json.dumps(snapshot)),
            )
    return (await get_experiment_by_id(experiment_id), None, None)


async def _build_experiment_snapshot(db, experiment_id: str) -> dict | None:
    snapshot = await db.execute(
        """SELECT id, flag_id, name, status::text, version, audience_fraction,
                  targeting_rule, created_by, created_at, updated_at
           FROM experiments WHERE id = $1""",
        (experiment_id,),
    )
    if not snapshot:
        return None
    snapshot["variants"] = await db.execute_all(
        "SELECT variant_name, variant_value, weight, is_control FROM experiment_variants WHERE experiment_id = $1",
        (experiment_id,),
    )
    snapshot["metrics"] = await db.execute_all(
        "SELECT metric_key, metric_type FROM experiment_metrics WHERE experiment_id = $1",
        (experiment_id,),
    )
    return serialize_json(snapshot)


async def add_experiment_variant(
    experiment_id: str,
    variant_name: str,
    variant_value: str,
    weight: float,
    is_control: bool = False,
) -> dict | None:
    async with Database() as db:
        r = await db.execute("SELECT status FROM experiments WHERE id = $1", (experiment_id,))
        if not r or r.get("status") != "draft":
            return None
        try:
            await db.execute(
                """INSERT INTO experiment_variants (experiment_id, variant_name, variant_value, weight, is_control)
                   VALUES ($1, $2, $3, $4, $5)""",
                (experiment_id, variant_name, variant_value, weight, is_control),
            )
        except asyncpg.PostgresError as e:
            msg = str(e).lower()
            if (
                "variant weights" in msg
                or "audience fraction" in msg
                or "весов вариантов" in msg
                or "долю аудитории" in msg
                or "exactly one control" in msg
            ):
                return None
            raise
        row = await db.execute(
            """SELECT id, experiment_id, variant_name, variant_value, weight, is_control, created_at
               FROM experiment_variants WHERE experiment_id = $1 AND variant_name = $2""",
            (experiment_id, variant_name),
        )
        return serialize_json(row)


async def update_experiment_variant(
    experiment_id: str,
    variant_id: str,
    variant_value: str | None = None,
    weight: float | None = None,
    is_control: bool | None = None,
) -> dict | None:
    async with Database() as db:
        r = await db.execute("SELECT status FROM experiments WHERE id = $1", (experiment_id,))
        if not r or r.get("status") != "draft":
            return None
        updates = []
        params = []
        idx = 1
        if variant_value is not None:
            updates.append(f"variant_value = ${idx}")
            params.append(variant_value)
            idx += 1
        if weight is not None:
            updates.append(f"weight = ${idx}")
            params.append(weight)
            idx += 1
        if is_control is not None:
            updates.append(f"is_control = ${idx}")
            params.append(is_control)
            idx += 1
        if not updates:
            row = await db.execute(
                "SELECT id, experiment_id, variant_name, variant_value, weight, is_control, created_at FROM experiment_variants WHERE id = $1 AND experiment_id = $2",
                (variant_id, experiment_id),
            )
            return serialize_json(row) if row else None
        params.extend([variant_id, experiment_id])
        await db.execute(
            f"UPDATE experiment_variants SET {', '.join(updates)} WHERE id = ${idx} AND experiment_id = ${idx + 1}",
            tuple(params),
        )
        row = await db.execute(
            "SELECT id, experiment_id, variant_name, variant_value, weight, is_control, created_at FROM experiment_variants WHERE id = $1 AND experiment_id = $2",
            (variant_id, experiment_id),
        )
        return serialize_json(row)


async def delete_experiment_variant(experiment_id: str, variant_id: str) -> bool:
    async with Database() as db:
        r = await db.execute("SELECT status FROM experiments WHERE id = $1", (experiment_id,))
        if not r or r["status"] != "draft":
            return False
        await db.execute(
            "DELETE FROM experiment_variants WHERE id = $1 AND experiment_id = $2",
            (variant_id, experiment_id),
        )
        return True


async def add_experiment_metric(
    experiment_id: str, metric_key: str, metric_type: str
) -> dict | None:
    if metric_type not in METRIC_TYPES:
        return None
    async with Database() as db:
        r = await db.execute("SELECT status FROM experiments WHERE id = $1", (experiment_id,))
        if not r or r["status"] != "draft":
            return None
        await db.execute(
            """INSERT INTO experiment_metrics (experiment_id, metric_key, metric_type)
               VALUES ($1, $2, $3)
               ON CONFLICT (experiment_id, metric_key, metric_type) DO NOTHING""",
            (experiment_id, metric_key, metric_type),
        )
        row = await db.execute(
            "SELECT id, experiment_id, metric_key, metric_type, created_at FROM experiment_metrics WHERE experiment_id = $1 AND metric_key = $2 AND metric_type = $3",
            (experiment_id, metric_key, metric_type),
        )
        return serialize_json(row)


async def _check_variant_weights_match_audience(db, experiment_id: str) -> str | None:
    row = await db.execute(
        """SELECT e.audience_fraction,
                  (SELECT COALESCE(SUM(ev.weight), 0) FROM experiment_variants ev WHERE ev.experiment_id = e.id) AS total_weight,
                  (SELECT COUNT(*) FROM experiment_variants ev WHERE ev.experiment_id = e.id) AS variant_count
           FROM experiments e WHERE e.id = $1""",
        (experiment_id,),
    )
    if not row:
        return None
    af = row.get("audience_fraction")
    total_weight = row.get("total_weight")
    variant_count = int(row.get("variant_count") or 0)
    if variant_count < 2:
        return None
    af_dec = Decimal(str(af)) if af is not None else None
    tw_dec = Decimal(str(total_weight)) if total_weight is not None else Decimal(0)
    if af_dec is None or tw_dec != af_dec:
        af_str = str(float(af_dec)) if af_dec is not None else "?"
        return (
            f"Сумма долей вариантов ({float(tw_dec)}) должна равняться доле аудитории (покрытию) эксперимента ({af_str}). "
            "Отправка на одобрение невозможна."
        )
    return None


async def submit_review(experiment_id: str) -> tuple[dict | None, str | None]:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not row or row["status"] != "draft":
            return (None, None)
        variant_count_row = await db.execute(
            "SELECT COUNT(*) AS c FROM experiment_variants WHERE experiment_id = $1",
            (experiment_id,),
        )
        variant_count = int((variant_count_row or {}).get("c") or 0)
        if variant_count < 1:
            return (None, "Добавьте хотя бы один вариант перед отправкой на одобрение.")
        err = await _check_variant_weights_match_audience(db, experiment_id)
        if err:
            return (None, err)
        await db.execute(
            "UPDATE experiments SET status = 'on_review', updated_at = NOW() WHERE id = $1",
            (experiment_id,),
        )
    return (await get_experiment_by_id(experiment_id), None)


async def get_review_approvals_count(experiment_id: str) -> int:
    async with Database() as db:
        count_row = await db.execute(
            "SELECT COUNT(*) AS c FROM experiment_review_history WHERE experiment_id = $1 AND action = 'approved'",
            (experiment_id,),
        )
        return count_row["c"]


async def check_access_to_experiment(experiment_id: str, user_id: str) -> bool:
    async with Database() as db:
        row = await db.execute(
            "SELECT created_by FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not row:
            return False

        created_by = row.get("created_by")
        if created_by is None:
            approver_group = await db.execute(
                "SELECT id FROM approver_groups WHERE experimenter_id IS NULL LIMIT 1"
            )
        else:
            approver_group = await db.execute(
                "SELECT id FROM approver_groups WHERE experimenter_id = $1",
                (str(created_by),),
            )
        if not approver_group:
            return False
        check_member = await db.execute_all(
            "SELECT 1 FROM approver_group_members WHERE approver_group_id = $1 AND approver_id = $2",
            (str(approver_group["id"]), str(user_id)),
        )
        return bool(check_member and len(check_member) > 0)


async def add_review_record(
    experiment_id: str, reviewer_id: str, action: str, comment: str | None = None
) -> dict | None:
    if action not in REVIEW_ACTIONS:
        return None
    async with Database() as db:
        exp = await db.execute(
            "SELECT id, status, created_by FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not exp or exp["status"] != "on_review":
            return None

        await db.execute(
            """INSERT INTO experiment_review_history (experiment_id, reviewer_id, action, comment)
               VALUES ($1, $2, $3, $4)""",
            (experiment_id, reviewer_id, action, comment),
        )
        if action == "requested_changes":
            await db.execute(
                "UPDATE experiments SET status = 'draft', updated_at = NOW() WHERE id = $1",
                (experiment_id,),
            )
        elif action == "rejected":
            await db.execute(
                "UPDATE experiments SET status = 'rejected', updated_at = NOW() WHERE id = $1",
                (experiment_id,),
            )
        elif action == "approved":
            from functions.users import get_approver_group_for_experimenter

            created_by = exp["created_by"]
            if created_by:
                group = await get_approver_group_for_experimenter(str(created_by))
                min_approvals = (group or {}).get("min_approvals", 1)
            else:
                min_approvals = 1
            count_row = await db.execute(
                "SELECT COUNT(*) AS c FROM experiment_review_history WHERE experiment_id = $1 AND action = 'approved'",
                (experiment_id,),
            )
            count = int((count_row or {}).get("c") or 0)
            if count >= min_approvals:
                await db.execute(
                    "UPDATE experiments SET status = 'approved', updated_at = NOW() WHERE id = $1",
                    (experiment_id,),
                )
            else:
                await db.execute(
                    "UPDATE experiments SET status = 'approved', updated_at = NOW() WHERE id = $1",
                    (experiment_id,),
                )
    return await get_experiment_by_id(experiment_id)


STATUS_TRANSITIONS = {
    "draft": ("on_review",),
    "on_review": ("draft", "rejected", "approved"),
    "approved": ("running",),
    "running": ("paused",),
    "paused": ("running",),
}


async def update_experiment_status(
    experiment_id: str,
    new_status: str,
    comment: str | None = None,
    reviewer_id: str | None = None,
) -> tuple[dict | None, str | None]:
    if new_status not in EXPERIMENT_STATUSES:
        return (None, None)
    experiment = await get_experiment_by_id(experiment_id)
    if not experiment:
        return (None, None)
    allowed = STATUS_TRANSITIONS.get(experiment["status"], ())
    if new_status not in allowed:
        return (None, None)
    if new_status == "on_review":
        return await submit_review(experiment_id)
    if new_status == "draft":
        updated = await add_review_record(experiment_id, reviewer_id, "requested_changes", comment)
        return (updated, None)
    if new_status == "rejected":
        updated = await add_review_record(experiment_id, reviewer_id, "rejected", comment)
        return (updated, None)
    if new_status == "approved":
        updated = await add_review_record(experiment_id, reviewer_id, "approved", comment)
        return (updated, None)
    if new_status == "running":
        updated = await start_experiment(experiment_id)
        return (updated, None)
    if new_status == "paused":
        updated = await pause_experiment(experiment_id)
        return (updated, None)
    return (None, None)


async def start_experiment(experiment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, flag_id, status FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not row or row["status"] not in ("approved", "paused"):
            return None

        if row["status"] != "paused":
            check_status = await db.execute(
                """SELECT 1 FROM experiments e
                   WHERE e.flag_id = (SELECT flag_id FROM experiments WHERE id = $1)
                     AND e.status IN ('running', 'paused')
                     AND e.id != $1""",
                (str(experiment_id),),
            )
            if check_status:
                return None

        await db.execute(
            "UPDATE experiments SET status = 'running', updated_at = NOW() WHERE id = $1",
            (experiment_id,),
        )
        return await get_experiment_by_id(experiment_id)


async def pause_experiment(experiment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not row or row["status"] != "running":
            return None
        await db.execute(
            "UPDATE experiments SET status = 'paused', updated_at = NOW() WHERE id = $1",
            (experiment_id,),
        )
        return await get_experiment_by_id(experiment_id)


COMPLETION_OUTCOMES = ("rollout_winner", "rollback", "no_effect")


async def rollback_experiment_to_control(experiment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not row or row["status"] not in ("running", "paused"):
            return None

        await db.execute("DELETE FROM decisions WHERE experiment_id = $1", (experiment_id,))
        await db.execute(
            "UPDATE experiments SET status = 'paused', updated_at = NOW() WHERE id = $1",
            (experiment_id,),
        )
        return await get_experiment_by_id(experiment_id)


async def complete_experiment(
    experiment_id: str,
    outcome: str,
    comment: str,
    winner_variant_id: str | None = None,
) -> dict | None:
    if outcome not in COMPLETION_OUTCOMES:
        return None
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1", (experiment_id,)
        )
        if not row or row["status"] not in ("running", "paused"):
            return None
        if outcome == "rollout_winner" and not winner_variant_id:
            return None
        await db.execute(
            """UPDATE experiments SET status = 'completed', updated_at = NOW(),
               completion_outcome = $2, completion_comment = $3, completion_winner_variant_id = $4
               WHERE id = $1""",
            (
                experiment_id,
                outcome,
                comment or "",
                winner_variant_id if outcome == "rollout_winner" else None,
            ),
        )
        return await _get_experiment_row_using_db(db, experiment_id)


async def get_review_history(experiment_id: str) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT h.id, h.experiment_id, h.reviewer_id, h.action, h.comment, h.created_at,
                      u.email AS reviewer_email, u.first_name AS reviewer_name
               FROM experiment_review_history h
               LEFT JOIN users u ON u.id = h.reviewer_id
               WHERE h.experiment_id = $1
               ORDER BY h.created_at ASC""",
            (experiment_id,),
        )
        return serialize_json(rows)


async def get_guardrail_history(experiment_id: str) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT id,
                      experiment_id,
                      metric_key,
                      threshold,
                      window_seconds,
                      action,
                      metric_value,
                      triggered_at,
                      details
               FROM experiment_guardrail_history
               WHERE experiment_id = $1
               ORDER BY triggered_at DESC""",
            (experiment_id,),
        )
        return serialize_json(rows)


async def record_guardrail_trigger(
    experiment_id: str,
    metric_key: str,
    threshold: float | None = None,
    window_seconds: int | None = None,
    action: str | None = None,
    metric_value: float | None = None,
    details: dict | None = None,
) -> dict | None:
    async with Database() as db:
        await db.execute(
            """INSERT INTO experiment_guardrail_history
                   (experiment_id, metric_key, threshold, window_seconds, action, metric_value, details)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            (experiment_id, metric_key, threshold, window_seconds, action, metric_value, details),
        )
        row = await db.execute(
            """SELECT id,
                      experiment_id,
                      metric_key,
                      threshold,
                      window_seconds,
                      action,
                      metric_value,
                      triggered_at,
                      details
               FROM experiment_guardrail_history
               WHERE experiment_id = $1
               ORDER BY triggered_at DESC
               LIMIT 1""",
            (experiment_id,),
        )
        return serialize_json(row)
