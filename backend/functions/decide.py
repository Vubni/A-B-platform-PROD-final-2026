import uuid
from decimal import Decimal
from typing import Any, Optional

from core import serialize_json
from database.database import Database
from dsl import evaluate_targeting_rule
from functions.flags import get_flag_by_key


async def get_decisions_for_subject(subject_id: str, attributes: dict[str, Any], flags: list[str]) -> list[dict[str, Any]]:
    async with Database() as db:
        result = {"flags": []}
        experiments = await db.execute_all(
            """SELECT e.id, e.name, e.status::text, e.version,
                    e.audience_fraction, e.targeting_rule,
                    e.created_by, f.id AS flag_id, f.key AS flag_key
            FROM experiments e
            JOIN feature_flags f ON e.flag_id = f.id
            WHERE e.status = 'running' AND f.key = ANY($1)""",
            (flags,),
        )
        if not experiments:
            for flag_id in flags:
                flag = await get_flag_by_key(flag_id)
                result["flags"].append({
                    "flag_key": flag['key'],
                    "flag_value": flag['default_value'],
                    "decision_id": None,
                    "experiment": None
                })
            return serialize_json(result)

        for experiment in experiments:
            flag = await get_flag_by_key(experiment['flag_key'])
            flag_id = experiment['flag_id']
            default_value = flag['default_value']

            if not evaluate_targeting_rule(experiment['targeting_rule'], attributes):
                decision_id = uuid.uuid4()
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, $5, NULL)""",
                    (decision_id, subject_id, flag_id, default_value, experiment['id']),
                )
                result["flags"].append({
                    "flag_key": experiment['flag_key'],
                    "flag_value": default_value,
                    "decision_id": str(decision_id),
                    "experiment": None
                })
                continue

            existing = await db.execute(
                """SELECT decision_id, value, experiment_id, variant_id
                   FROM decisions WHERE subject_id = $1 AND flag_id = $2
                   ORDER BY created_at DESC LIMIT 1""",
                (subject_id, flag_id))
            if existing:
                out_value = existing["value"]
                out_experiment_id = str(existing["experiment_id"]) if existing.get("experiment_id") else None
                out_variant = None
                if existing.get("variant_id"):
                    vrow = await db.execute(
                        "SELECT variant_name FROM experiment_variants WHERE id = $1",
                        (existing["variant_id"],),
                    )
                    out_variant = vrow["variant_name"] if vrow else None

                decision_id = uuid.uuid4()
                exp_id = existing.get("experiment_id") if existing.get("experiment_id") is not None else experiment["id"]
                var_id = existing.get("variant_id")
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    (decision_id, subject_id, flag_id, out_value, exp_id, var_id),
                )
                result["flags"].append({
                    "flag_key": experiment['flag_key'],
                    "flag_value": out_value,
                    "decision_id": str(decision_id),
                    "experiment": {
                        "experiment_id": out_experiment_id,
                        "variant": out_variant
                    }
                })
                continue



            audience_fraction = serialize_json(experiment['audience_fraction'])
            counts = await db.execute(
                """SELECT
                    COUNT(*) AS total,
                    COUNT(variant_id) FILTER (WHERE experiment_id = $2 AND variant_id IS NOT NULL) AS in_experiment
                   FROM decisions WHERE flag_id = $1""",
                (flag_id, experiment['id']),
            )
            total = counts["total"] or 0
            in_experiment = counts["in_experiment"] or 0
            assign_to_experiment = (in_experiment / max(total, 1)) < audience_fraction

            decision_id = str(uuid.uuid4())
            if not assign_to_experiment:
                await db.execute(
                    """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                       VALUES ($1, $2, $3, $4, NULL, NULL)""",
                    (uuid.UUID(decision_id), subject_id, flag_id, default_value),
                )
                result["flags"].append({
                    "flag_key": experiment['flag_key'],
                    "flag_value": default_value,
                    "decision_id": decision_id,
                    "experiment": None
                })
                continue

            variants = await db.execute_all(
                """SELECT id, variant_name, variant_value, weight
                   FROM experiment_variants WHERE experiment_id = $1 ORDER BY variant_name""",
                (experiment['id'],),
            )

            variant_counts = await db.execute_all(
                """SELECT variant_id, COUNT(*) AS cnt
                   FROM decisions WHERE experiment_id = $1 AND variant_id IS NOT NULL
                   GROUP BY variant_id""",
                (experiment['id'],),
            )
            count_by_variant: dict[str, int] = {str(r["variant_id"]): r["cnt"] for r in (variant_counts or [])}
            total_in_exp = in_experiment
            af = audience_fraction

            best_variant = None
            best_deficit = -1.0
            for v in variants:
                vid = str(v["id"])
                target_ratio = serialize_json(v["weight"]) / af
                current_ratio = (count_by_variant.get(vid, 0) / max(total_in_exp, 1))
                deficit = target_ratio - current_ratio
                if deficit > best_deficit:
                    best_deficit = deficit
                    best_variant = v

            variant_value = best_variant["variant_value"]
            variant_id = best_variant["id"]

            await db.execute(
                """INSERT INTO decisions (decision_id, subject_id, flag_id, value, experiment_id, variant_id)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                (uuid.UUID(decision_id), subject_id, flag_id, variant_value, experiment['id'], variant_id),
            )
            result["flags"].append({
                "flag_key": experiment['flag_key'],
                "flag_value": variant_value,
                "decision_id": decision_id,
                "experiment": {
                    "experiment_id": str(experiment['id']),
                    "variant": best_variant["variant_name"]
                }
            })

        added_keys = {r["flag_key"] for r in result["flags"]}
        for flag_id in flags:
            flag = await get_flag_by_key(flag_id)
            if not flag or flag["key"] in added_keys:
                continue
            result["flags"].append({
                "flag_key": flag["key"],
                "flag_value": flag["default_value"],
                "decision_id": None,
                "experiment": None,
            })

        return serialize_json(result)