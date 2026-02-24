import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from autopilot_ramp.ramp_evaluator import sync_and_tick_autopilot
from config import (
    EXPERIMENT_COOLDOWN_SECONDS,
    MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT,
)
from core import serialize_json
from database.database import Database
from dsl import evaluate_targeting_rule
from functions.conflicts import resolve_experiment_conflicts, store_conflict_logs
from functions.flags import cast_flag_value, get_flag_by_key


async def get_decisions_for_subject(
    subject_id: str, attributes: dict[str, Any], flags: list[str]
) -> list[dict[str, Any]]:
    async with Database() as db:
        result = {"flags": []}
        experiments = await db.execute_all(
            """SELECT e.id,
                      e.name,
                      e.status::text,
                      e.version,
                      e.audience_fraction,
                      e.targeting_rule,
                      e.created_by,
                      f.id AS flag_id,
                      f.key AS flag_key,
                      f.value_type::text AS value_type
               FROM experiments e
               JOIN feature_flags f ON e.flag_id = f.id
               WHERE e.status = 'running' AND f.key = ANY($1)""",
            (flags,),
        )
        if not experiments:
            for flag_key in flags:
                flag = await get_flag_by_key(flag_key)
                if not flag:
                    continue
                decision_id = uuid.uuid4()
                flag_uuid = uuid.UUID(flag["id"]) if isinstance(flag["id"], str) else flag["id"]
                raw_default = flag["default_value"]
                value_type = flag.get("value_type") or "string"
                flag_value = cast_flag_value(value_type, str(raw_default))
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, NULL, NULL)""",
                    (decision_id, subject_id, flag_uuid, raw_default),
                )
                result["flags"].append(
                    {
                        "flag_key": flag["key"],
                        "flag_value": flag_value,
                        "decision_id": str(decision_id),
                        "experiment": None,
                    }
                )
            return serialize_json(result)

        (
            allowed_experiment_ids,
            conflict_logs,
            blocked_by_domain,
        ) = await resolve_experiment_conflicts(
            db=db, subject_id=subject_id, experiments=experiments
        )
        if conflict_logs:
            await store_conflict_logs(db=db, subject_id=subject_id, logs=conflict_logs)

        for experiment in experiments:
            if str(experiment["id"]) not in allowed_experiment_ids:
                flag = await get_flag_by_key(experiment["flag_key"])
                raw_default = flag["default_value"] if flag else ""
                value_type = (
                    (flag or {}).get("value_type") or experiment.get("value_type") or "string"
                )
                flag_value = cast_flag_value(value_type, str(raw_default))
                decision_id = uuid.uuid4()
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, NULL, NULL)""",
                    (decision_id, subject_id, experiment["flag_id"], raw_default),
                )
                result["flags"].append(
                    {
                        "flag_key": experiment["flag_key"],
                        "flag_value": flag_value,
                        "decision_id": str(decision_id),
                        "experiment": None,
                        "conflict_lost": True,
                        "conflict_domain": blocked_by_domain.get(str(experiment["id"])),
                    }
                )
                continue
            await sync_and_tick_autopilot(str(experiment["id"]))
            fresh = await db.execute(
                """SELECT audience_fraction FROM experiments WHERE id = $1""", (experiment["id"],)
            )
            experiment["audience_fraction"] = fresh["audience_fraction"]

            flag = await get_flag_by_key(experiment["flag_key"])
            flag_id = experiment["flag_id"]
            raw_default = flag["default_value"]
            value_type = flag.get("value_type") or experiment.get("value_type") or "string"
            default_value_typed = cast_flag_value(value_type, str(raw_default))

            if not evaluate_targeting_rule(experiment["targeting_rule"], attributes):
                decision_id = uuid.uuid4()
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, $5, NULL)""",
                    (decision_id, subject_id, flag_id, raw_default, experiment["id"]),
                )
                result["flags"].append(
                    {
                        "flag_key": experiment["flag_key"],
                        "flag_value": default_value_typed,
                        "decision_id": str(decision_id),
                        "experiment": None,
                    }
                )
                continue

            existing = await db.execute(
                """SELECT decision_id, value, experiment_id, variant_id
                   FROM decisions WHERE subject_id = $1 AND flag_id = $2
                   ORDER BY created_at DESC LIMIT 1""",
                (subject_id, flag_id),
            )

            active_count_row = await db.execute(
                """SELECT COUNT(DISTINCT d.experiment_id) AS cnt
                   FROM decisions d
                   JOIN experiments e ON e.id = d.experiment_id AND e.status = 'running'
                   WHERE d.subject_id = $1 AND d.variant_id IS NOT NULL""",
                (subject_id,),
            )
            active_experiments_count = (active_count_row or {}).get("cnt") or 0
            if active_experiments_count >= MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT and not existing:
                decision_id = uuid.uuid4()
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, NULL, NULL)""",
                    (decision_id, subject_id, flag_id, raw_default),
                )
                result["flags"].append(
                    {
                        "flag_key": experiment["flag_key"],
                        "flag_value": default_value_typed,
                        "decision_id": str(decision_id),
                        "experiment": None,
                    }
                )
                continue

            if existing:
                existing_raw_value = existing["value"]
                out_experiment_id = (
                    str(existing["experiment_id"]) if existing.get("experiment_id") else None
                )
                out_flag_value = cast_flag_value(value_type, str(existing_raw_value))
                out_variant = None
                if existing.get("variant_id"):
                    vrow = await db.execute(
                        "SELECT variant_name FROM experiment_variants WHERE id = $1",
                        (existing["variant_id"],),
                    )
                    out_variant = vrow["variant_name"] if vrow else None

                decision_id = uuid.uuid4()
                exp_id = (
                    existing.get("experiment_id")
                    if existing.get("experiment_id") is not None
                    else experiment["id"]
                )
                var_id = existing.get("variant_id")
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    (decision_id, subject_id, flag_id, existing_raw_value, exp_id, var_id),
                )
                result["flags"].append(
                    {
                        "flag_key": experiment["flag_key"],
                        "flag_value": out_flag_value,
                        "decision_id": str(decision_id),
                        "experiment": {"experiment_id": out_experiment_id, "variant": out_variant},
                    }
                )
                continue

            audience_fraction = experiment["audience_fraction"]
            counts = await db.execute(
                """SELECT
                    COUNT(*) AS total,
                    COUNT(variant_id) FILTER (WHERE experiment_id = $2 AND variant_id IS NOT NULL) AS in_experiment
                   FROM decisions WHERE flag_id = $1""",
                (flag_id, experiment["id"]),
            )
            total = counts["total"] or 0
            in_experiment = counts["in_experiment"] or 0

            if total == 0:
                assign_to_experiment = False
            elif audience_fraction == 0:
                assign_to_experiment = True
            else:
                target_in_experiment = (total + 1) * audience_fraction
                assign_to_experiment = in_experiment < target_in_experiment

            if assign_to_experiment:
                cooldown_row = await db.execute(
                    "SELECT entered_at FROM subject_experiment_cooldown WHERE subject_id = $1",
                    (subject_id,),
                )
                if cooldown_row and cooldown_row.get("entered_at"):
                    entered_at = cooldown_row["entered_at"]
                    if getattr(entered_at, "tzinfo", None) is None:
                        entered_at = entered_at.replace(tzinfo=UTC)
                    now_utc = datetime.now(UTC)
                    if (now_utc - entered_at).total_seconds() < EXPERIMENT_COOLDOWN_SECONDS:
                        assign_to_experiment = False

            decision_id = str(uuid.uuid4())
            if not assign_to_experiment:
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, NULL, NULL)""",
                    (uuid.UUID(decision_id), subject_id, flag_id, raw_default),
                )
                result["flags"].append(
                    {
                        "flag_key": experiment["flag_key"],
                        "flag_value": default_value_typed,
                        "decision_id": decision_id,
                        "experiment": None,
                    }
                )
                continue

            variants = await db.execute_all(
                """SELECT id, variant_name, variant_value, weight
                   FROM experiment_variants WHERE experiment_id = $1 ORDER BY variant_name""",
                (experiment["id"],),
            )

            variant_counts = await db.execute_all(
                """SELECT variant_id, COUNT(*) AS cnt
                   FROM decisions WHERE experiment_id = $1 AND variant_id IS NOT NULL
                   GROUP BY variant_id""",
                (experiment["id"],),
            )
            count_by_variant: dict[str, int] = {
                str(r["variant_id"]): r["cnt"] for r in (variant_counts or [])
            }
            total_in_exp = in_experiment
            af = audience_fraction

            best_variant = None
            best_deficit = Decimal("-1")
            for v in variants:
                vid = str(v["id"])
                weight = Decimal(str(serialize_json(v["weight"])))
                target_ratio = weight / af if af else Decimal("0")
                current_ratio = Decimal(count_by_variant.get(vid, 0)) / max(
                    Decimal(total_in_exp), 1
                )
                deficit = target_ratio - current_ratio
                if deficit > best_deficit:
                    best_deficit = deficit
                    best_variant = v

            raw_variant_value = best_variant["variant_value"]
            variant_id = best_variant["id"]
            flag_value = cast_flag_value(value_type, str(raw_variant_value))

            await db.execute(
                """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                (
                    uuid.UUID(decision_id),
                    subject_id,
                    flag_id,
                    raw_variant_value,
                    experiment["id"],
                    variant_id,
                ),
            )
            after_count_row = await db.execute(
                """SELECT COUNT(DISTINCT d.experiment_id) AS cnt
                   FROM decisions d
                   JOIN experiments e ON e.id = d.experiment_id AND e.status = 'running'
                   WHERE d.subject_id = $1 AND d.variant_id IS NOT NULL""",
                (subject_id,),
            )
            if ((after_count_row or {}).get("cnt") or 0) >= MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT:
                await db.execute(
                    """INSERT INTO subject_experiment_cooldown (subject_id, entered_at)
                       VALUES ($1, NOW()) ON CONFLICT (subject_id) DO UPDATE SET entered_at = NOW()""",
                    (subject_id,),
                )
            result["flags"].append(
                {
                    "flag_key": experiment["flag_key"],
                    "flag_value": flag_value,
                    "decision_id": decision_id,
                    "experiment": {
                        "experiment_id": str(experiment["id"]),
                        "variant": best_variant["variant_name"],
                    },
                }
            )

        added_keys = {r["flag_key"] for r in result["flags"]}
        for flag_key in flags:
            flag = await get_flag_by_key(flag_key)
            if not flag or flag["key"] in added_keys:
                continue
            decision_id = uuid.uuid4()
            flag_uuid = uuid.UUID(flag["id"]) if isinstance(flag["id"], str) else flag["id"]
            raw_default = flag["default_value"]
            value_type = flag.get("value_type") or "string"
            flag_value = cast_flag_value(value_type, str(raw_default))
            await db.execute(
                """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                   VALUES ($1, $2, $3, $4, NULL, NULL)""",
                (decision_id, subject_id, flag_uuid, raw_default),
            )
            result["flags"].append(
                {
                    "flag_key": flag["key"],
                    "flag_value": flag_value,
                    "decision_id": str(decision_id),
                    "experiment": None,
                }
            )

        return serialize_json(result)
