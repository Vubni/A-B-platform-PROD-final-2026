from decimal import Decimal
from typing import Any, Optional

from core import serialize_json
from database.database import Database

EXPERIMENT_STATUSES = (
    "draft", "on_review", "approved", "running", "paused",
    "completed", "archived", "rejected",
)
METRIC_TYPES = ("primary", "auxiliary", "guardrail")
REVIEW_ACTIONS = ("approved", "requested_changes", "rejected")


async def create_experiment(flag_id: str, name: str, audience_fraction: float, created_by: Optional[str] = None, targeting_rule: Optional[str] = None, primary_metric_key: Optional[str] = None) -> Optional[dict]:
    async with Database() as db:
        flag_row = await db.execute("SELECT id FROM feature_flags WHERE id = $1 AND name = $2", (flag_id, name))
        if not flag_row:
            return None
        await db.execute(
            """INSERT INTO experiments (flag_id, name, audience_fraction, targeting_rule, primary_metric_key, created_by)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            (flag_id, name, audience_fraction, targeting_rule, primary_metric_key, created_by),
        )
        return await get_experiment_by_id(flag_id)


async def get_experiment_by_id(experiment_id: str) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute(
            """SELECT e.id, e.flag_id, e.name, e.status::text, e.version,
                      e.audience_fraction, e.targeting_rule, e.primary_metric_key,
                      e.created_by, e.created_at, e.updated_at,
                      f.key AS flag_key
               FROM experiments e
               JOIN feature_flags f ON f.id = e.flag_id
               WHERE e.id = $1""",
            (experiment_id,))
        if not row:
            return None
        row["variants"] = await db.execute_all(
            """SELECT id, experiment_id, variant_name, variant_value, weight, is_control, created_at
               FROM experiment_variants WHERE experiment_id = $1 ORDER BY variant_name""",
            (experiment_id,))
        row["metrics"] = await db.execute_all(
            """SELECT id, experiment_id, metric_key, metric_type, created_at
               FROM experiment_metrics WHERE experiment_id = $1""",
            (experiment_id,))
        return serialize_json(row)


async def get_experiments_list(flag_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
    async with Database() as db:
        sql = """SELECT e.id, e.flag_id, e.name, e.status::text, e.version,
                        e.audience_fraction, e.targeting_rule, e.primary_metric_key,
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
        return rows


async def update_experiment(experiment_id: str, name: Optional[str] = None, audience_fraction: Optional[float] = None, targeting_rule: Optional[str] = None, primary_metric_key: Optional[str] = None) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status, version FROM experiments WHERE id = $1",
            (experiment_id,),
        )
        if not row or row.get("status") != "draft":
            return None
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
        if primary_metric_key is not None:
            updates.append(f"primary_metric_key = ${idx}")
            params.append(primary_metric_key)
            idx += 1
        if len(params) == 0:
            return await get_experiment_by_id(experiment_id)
        new_version = (row.get("version") or 1) + 1
        updates.append(f"version = ${idx}")
        params.append(new_version)
        idx += 1
        params.append(experiment_id)
        await db.execute(
            f"UPDATE experiments SET {', '.join(updates)} WHERE id = ${idx}",
            tuple(params),
        )
        snapshot = await _build_experiment_snapshot(db, experiment_id)
        if snapshot:
            await db.execute(
                """INSERT INTO experiment_version_snapshots (experiment_id, version, snapshot)
                   VALUES ($1, $2, $3)""",
                (experiment_id, new_version, snapshot),
            )
        return await get_experiment_by_id(experiment_id)


async def _build_experiment_snapshot(db, experiment_id: str) -> Optional[dict]:
    snapshot = await db.execute(
        """SELECT id, flag_id, name, status::text, version, audience_fraction,
                  targeting_rule, primary_metric_key, created_by, created_at, updated_at
           FROM experiments WHERE id = $1""",
        (experiment_id,))
    if not snapshot:
        return None
    snapshot["variants"] = await db.execute_all(
        "SELECT variant_name, variant_value, weight, is_control FROM experiment_variants WHERE experiment_id = $1",
        (experiment_id,))
    snapshot["metrics"] = await db.execute_all(
        "SELECT metric_key, metric_type FROM experiment_metrics WHERE experiment_id = $1",
        (experiment_id,))
    return serialize_json(snapshot)


async def add_experiment_variant(experiment_id: str, variant_name: str, variant_value: str, weight: float, is_control: bool = False) -> Optional[dict]:
    async with Database() as db:
        r = await db.execute("SELECT status FROM experiments WHERE id = $1", (experiment_id,))
        if not r or r.get("status") != "draft":
            return None
        await db.execute(
            """INSERT INTO experiment_variants (experiment_id, variant_name, variant_value, weight, is_control)
               VALUES ($1, $2, $3, $4, $5)""",
            (experiment_id, variant_name, variant_value, weight, is_control),
        )
        row = await db.execute(
            """SELECT id, experiment_id, variant_name, variant_value, weight, is_control, created_at
               FROM experiment_variants WHERE experiment_id = $1 AND variant_name = $2""",
            (experiment_id, variant_name),
        )
        return serialize_json(row)


async def update_experiment_variant(experiment_id: str, variant_id: str, variant_value: Optional[str] = None, weight: Optional[float] = None, is_control: Optional[bool] = None) -> Optional[dict]:
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
            (variant_id, experiment_id))
        return True


async def add_experiment_metric(experiment_id: str, metric_key: str, metric_type: str) -> Optional[dict]:
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
            (experiment_id, metric_key, metric_type))
        row = await db.execute(
            "SELECT id, experiment_id, metric_key, metric_type, created_at FROM experiment_metrics WHERE experiment_id = $1 AND metric_key = $2 AND metric_type = $3",
            (experiment_id, metric_key, metric_type))
        return serialize_json(row)


async def submit_review(experiment_id: str) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1",
            (experiment_id,))
        if not row or row["status"] != "draft":
            return None
        variant_count = await db.execute(
            "SELECT COUNT(*) AS c FROM experiment_variants WHERE experiment_id = $1",
            (experiment_id,))
        if variant_count["c"] < 1:
            return None
        await db.execute(
            "UPDATE experiments SET status = 'on_review', updated_at = NOW() WHERE id = $1",
            (experiment_id,))
        return await get_experiment_by_id(experiment_id)


async def get_review_approvals_count(experiment_id: str) -> int:
    async with Database() as db:
        count_row = await db.execute(
            "SELECT COUNT(*) AS c FROM experiment_review_history WHERE experiment_id = $1 AND action = 'approved'",
            (experiment_id,))
        return count_row["c"]


async def check_access_to_experiment(experiment_id: str, user_id: str) -> bool:
    async with Database() as db:
        row = await db.execute(
            "SELECT created_by FROM experiments WHERE id = $1",
            (experiment_id,))
        if not row:
            return False
            
        approver_group = await db.execute(
            "SELECT id FROM approver_groups WHERE experimenter_id = $1", (row["created_by"],))
        if not approver_group:
            return False
        check_member = await db.execute_all(
            "SELECT 1 FROM approver_group_members WHERE approver_group_id = $1 and approver_id = $2",
            (approver_group["id"], user_id))
        return check_member is not None

async def add_review_record(experiment_id: str, reviewer_id: str, action: str, comment: Optional[str] = None) -> Optional[dict]:
    if action not in REVIEW_ACTIONS:
        return None
    async with Database() as db:
        exp = await db.execute(
            "SELECT id, status, created_by FROM experiments WHERE id = $1",
            (experiment_id,))
        if not exp or exp["status"] != "on_review":
            return None


        await db.execute(
            """INSERT INTO experiment_review_history (experiment_id, reviewer_id, action, comment)
               VALUES ($1, $2, $3, $4)""",
            (experiment_id, reviewer_id, action, comment))
        if action == "requested_changes":
            await db.execute(
                "UPDATE experiments SET status = 'draft', updated_at = NOW() WHERE id = $1",
                (experiment_id,))
        elif action == "rejected":
            await db.execute(
                "UPDATE experiments SET status = 'rejected', updated_at = NOW() WHERE id = $1",
                (experiment_id,))
        elif action == "approved":
            from functions.users import get_approver_group_for_experimenter
            created_by = exp["created_by"]
            if created_by:
                group = await get_approver_group_for_experimenter(str(created_by))
                min_approvals = group["min_approvals"]
            else:
                min_approvals = 1
            count_row = await db.execute(
                "SELECT COUNT(*) AS c FROM experiment_review_history WHERE experiment_id = $1 AND action = 'approved'",
                (experiment_id,))
            count = int(count_row["c"])
            if count >= min_approvals:
                await db.execute(
                    "UPDATE experiments SET status = 'approved', updated_at = NOW() WHERE id = $1",
                    (experiment_id,))
        return await get_experiment_by_id(experiment_id)


STATUS_TRANSITIONS = {
    "draft": ("on_review",),
    "on_review": ("draft", "rejected", "approved"),
    "approved": ("running",),
    "running": ("paused", "completed"),
    "paused": ("running", "completed"),
}


async def update_experiment_status(experiment_id: str, new_status: str, comment: Optional[str] = None, reviewer_id: Optional[str] = None) -> Optional[dict]:
    if new_status not in EXPERIMENT_STATUSES:
        return None
    experiment = await get_experiment_by_id(experiment_id)
    if not experiment:
        return None
    allowed = STATUS_TRANSITIONS.get(experiment["status"], ())
    if new_status not in allowed:
        return None
    if new_status == "on_review":
        return await submit_review(experiment_id)
    if new_status == "draft":
        return await add_review_record(experiment_id, reviewer_id, "requested_changes", comment)
    if new_status == "rejected":
        return await add_review_record(experiment_id, reviewer_id, "rejected", comment)
    if new_status == "approved":
        return await add_review_record(experiment_id, reviewer_id, "approved", comment)
    if new_status == "running":
        return await start_experiment(experiment_id)
    if new_status == "paused":
        return await pause_experiment(experiment_id)
    if new_status == "completed":
        return await complete_experiment(experiment_id)
    return None


async def start_experiment(experiment_id: str) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, flag_id, status FROM experiments WHERE id = $1",
            (experiment_id,))
        if not row or row["status"] not in ("approved", "paused"):
            return None
        
        if row["status"] != "paused":
            check_status = await db.execute("SELECT 1 FROM experiments WHERE flag_id = $1 AND status in ('running', 'paused')", (row["flag_id"],))
            if check_status:
                return None

        await db.execute(
            "UPDATE experiments SET status = 'running', updated_at = NOW() WHERE id = $1",
            (experiment_id,))
        return await get_experiment_by_id(experiment_id)


async def pause_experiment(experiment_id: str) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1",
            (experiment_id,))
        if not row or row["status"] != "running":
            return None
        await db.execute(
            "UPDATE experiments SET status = 'paused', updated_at = NOW() WHERE id = $1",
            (experiment_id,))
        return await get_experiment_by_id(experiment_id)


async def complete_experiment(experiment_id: str) -> Optional[dict]:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, status FROM experiments WHERE id = $1",
            (experiment_id,))
        if not row or row["status"] not in ("running", "paused"):
            return None
        await db.execute(
            "UPDATE experiments SET status = 'completed', updated_at = NOW() WHERE id = $1",
            (experiment_id,))
        return await get_experiment_by_id(experiment_id)


async def get_review_history(experiment_id: str) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT h.id, h.experiment_id, h.reviewer_id, h.action, h.comment, h.created_at,
                      u.email AS reviewer_email, u.first_name AS reviewer_name
               FROM experiment_review_history h
               LEFT JOIN users u ON u.id = h.reviewer_id
               WHERE h.experiment_id = $1
               ORDER BY h.created_at ASC""",
            (experiment_id,))
        return serialize_json(rows)


async def get_guardrail_history(experiment_id: str) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT id, experiment_id, metric_key, triggered_at, details
               FROM experiment_guardrail_history
               WHERE experiment_id = $1
               ORDER BY triggered_at DESC""",
            (experiment_id,))
        return serialize_json(rows)


async def record_guardrail_trigger(experiment_id: str, metric_key: str, details: Optional[dict] = None) -> Optional[dict]:
    async with Database() as db:
        await db.execute(
            "INSERT INTO experiment_guardrail_history (experiment_id, metric_key, details) VALUES ($1, $2, $3)",
            (experiment_id, metric_key, details))
        row = await db.execute(
            "SELECT id, experiment_id, metric_key, triggered_at, details FROM experiment_guardrail_history WHERE experiment_id = $1 ORDER BY triggered_at DESC LIMIT 1",
            (experiment_id,))
        return serialize_json(row)
