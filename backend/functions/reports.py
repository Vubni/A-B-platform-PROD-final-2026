from datetime import datetime
from typing import Any, Optional

from database.database import Database
from functions.experiments import get_experiment_by_id
from functions.event_types import get_event_type_by_key
from functions.metrics import get_metric_by_key


def _metric_event_type_keys(metric_catalog_row: dict, catalog_by_key: dict[str, dict]) -> set[str]:
    keys: set[str] = set()
    rule = metric_catalog_row.get("aggregation_rule") or {}
    kind = (rule.get("kind") or "").strip()
    if kind in ("count_events", "avg", "percentile"):
        ek = rule.get("event_type_key")
        if ek:
            keys.add(ek.strip())
    elif kind == "ratio":
        for mkey in (rule.get("numerator_metric_key"), rule.get("denominator_metric_key")):
            if mkey and mkey in catalog_by_key:
                keys |= _metric_event_type_keys(catalog_by_key[mkey], catalog_by_key)
    return keys


def _parse_iso(s: str) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


async def _decision_ids_by_variant(db, experiment_id: str, variant_id: str) -> list[str]:
    rows = await db.execute_all(
        """SELECT decision_id FROM decisions
           WHERE experiment_id = $1 AND variant_id = $2""",
        (experiment_id, variant_id))
    return [r["decision_id"] for r in rows]


async def _event_counts_by_type(
    db, decision_ids: list[str], event_type_keys: list[str], start_ts: datetime, end_ts: datetime
) -> dict[str, int]:
    if not decision_ids or not event_type_keys:
        return {k: 0 for k in event_type_keys}
    key_to_id: dict[str, str] = {}
    for k in event_type_keys:
        et = await get_event_type_by_key(k, active_only=False)
        if et and et.get("id"):
            key_to_id[k] = et["id"]
    if not key_to_id:
        return {k: 0 for k in event_type_keys}
    ids = list(key_to_id.values())
    rows = await db.execute_all(
        """SELECT e.event_type_id, COUNT(*) AS cnt
           FROM event_occurrences e
           WHERE e.decision_id = ANY($1::uuid[]) AND e.event_type_id = ANY($2::uuid[])
             AND e.timestamp >= $3 AND e.timestamp < $4
           GROUP BY e.event_type_id""",
        (decision_ids, ids, start_ts, end_ts),
    )
    id_to_key = {v: k for k, v in key_to_id.items()}
    result = {k: 0 for k in event_type_keys}
    for r in rows:
        eid = r.get("event_type_id")
        if eid and eid in id_to_key:
            result[id_to_key[eid]] = int(r.get("cnt") or 0)
    return result


async def _compute_count_events(db, decision_ids: list[str], event_type_id: str, start_ts: datetime,
    end_ts: datetime, aggregation_unit: str) -> Optional[float]:
    if not decision_ids:
        return 0.0
    if aggregation_unit == "subject":
        row = await db.execute(
            """SELECT COUNT(DISTINCT e.subject_id) AS cnt
               FROM event_occurrences e
               WHERE e.decision_id = ANY($1::uuid[]) AND e.event_type_id = $2
                 AND e.timestamp >= $3 AND e.timestamp < $4""",
            (decision_ids, event_type_id, start_ts, end_ts),
        )
    else:
        row = await db.execute(
            """SELECT COUNT(*) AS cnt FROM event_occurrences e
               WHERE e.decision_id = ANY($1::uuid[]) AND e.event_type_id = $2
                 AND e.timestamp >= $3 AND e.timestamp < $4""",
            (decision_ids, event_type_id, start_ts, end_ts),
        )
    return float(row["cnt"]) if row and row.get("cnt") is not None else None


def _payload_key_from_value_path(value_path: str) -> str:
    s = (value_path or "").strip()
    if "." in s:
        return s.split(".")[-1]
    return s or "duration_ms"


async def _compute_avg(db, decision_ids: list[str], event_type_id: str, start_ts: datetime,
    end_ts: datetime, value_path: str) -> Optional[float]:
    if not decision_ids:
        return None
    payload_key = _payload_key_from_value_path(value_path)
    row = await db.execute(
        """SELECT AVG((e.payload->>$5)::float) AS val
           FROM event_occurrences e
           WHERE e.decision_id = ANY($1::uuid[]) AND e.event_type_id = $2
             AND e.timestamp >= $3 AND e.timestamp < $4
             AND e.payload ? $5""",
        (decision_ids, event_type_id, start_ts, end_ts, payload_key))
    if not row or row.get("val") is None:
        return None
    return float(row["val"])


async def _compute_percentile(db, decision_ids: list[str], event_type_id: str, start_ts: datetime,
    end_ts: datetime, value_path: str, percentile: int) -> Optional[float]:
    if not decision_ids:
        return None
    payload_key = _payload_key_from_value_path(value_path)
    row = await db.execute(
        """SELECT PERCENTILE_CONT($6::float / 100.0) WITHIN GROUP (ORDER BY (e.payload->>$5)::float) AS val
           FROM event_occurrences e
           WHERE e.decision_id = ANY($1::uuid[]) AND e.event_type_id = $2
             AND e.timestamp >= $3 AND e.timestamp < $4
             AND e.payload ? $5""",
        (decision_ids, event_type_id, start_ts, end_ts, payload_key, percentile))
    if not row or row.get("val") is None:
        return None
    return float(row["val"])


async def _compute_metric_value(db, decision_ids: list[str], start_ts: datetime, end_ts: datetime, metric_catalog_row: dict,) -> Optional[float]:
    rule = metric_catalog_row.get("aggregation_rule") or {}
    kind = (rule.get("kind") or "").strip()
    event_type_key = rule.get("event_type_key")
    if not event_type_key:
        return None
    et = await get_event_type_by_key(event_type_key, active_only=False)
    if not et:
        return None
    event_type_id = et.get("id")
    aggregation_unit = (rule.get("aggregation_unit") or "event").strip()

    if kind == "count_events":
        return await _compute_count_events(
            db, decision_ids, event_type_id, start_ts, end_ts, aggregation_unit
        )
    if kind == "avg":
        value_path = rule.get("value_path") or "payload.duration_ms"
        return await _compute_avg(
            db, decision_ids, event_type_id, start_ts, end_ts, value_path
        )
    if kind == "percentile":
        value_path = rule.get("value_path") or "payload.duration_ms"
        return await _compute_percentile(
            db, decision_ids, event_type_id, start_ts, end_ts, value_path, int(rule.get("percentile") or 95)
        )
    if kind == "ratio":
        num_key = rule.get("numerator_metric_key")
        den_key = rule.get("denominator_metric_key")
        if not num_key or not den_key:
            return None
        num_metric = await get_metric_by_key(num_key)
        den_metric = await get_metric_by_key(den_key)
        if not num_metric or not den_metric:
            return None
        num_val = await _compute_metric_value(db, decision_ids, start_ts, end_ts, num_metric)
        den_val = await _compute_metric_value(db, decision_ids, start_ts, end_ts, den_metric)
        if num_val is None or den_val is None or den_val == 0:
            return None
        return num_val / den_val
    return None


def _primary_metric_summary(
    variants: list[dict],
    report_variants: list[dict],
    primary_metric_key: str,
    primary_metric_name: Optional[str],
    event_expectations: Optional[dict],
) -> Optional[dict]:
    """Сводка по главной метрике: лучше/хуже по каждому варианту относительно контроля."""
    if not event_expectations or not isinstance(event_expectations, dict):
        direction = None
    else:
        for v in event_expectations.values():
            if isinstance(v, str) and v.strip().lower() in ("higher", "lower"):
                direction = v.strip().lower()
                break
        else:
            direction = None
    control_value = None
    control_variant_name = None
    for v, rv in zip(variants, report_variants):
        if v.get("is_control"):
            for mv in rv.get("metric_values") or []:
                if mv.get("metric_key") == primary_metric_key:
                    control_value = mv.get("value")
                    control_variant_name = v.get("variant_name") or ""
                    break
            break
    if control_value is None and direction is not None:
        direction = None
    results = []
    for v, rv in zip(variants, report_variants):
        if v.get("is_control"):
            continue
        var_name = v.get("variant_name") or ""
        value = None
        for mv in rv.get("metric_values") or []:
            if mv.get("metric_key") == primary_metric_key:
                value = mv.get("value")
                break
        vs_control = "same"
        change_percent = None
        if value is not None and control_value is not None and direction:
            if isinstance(control_value, (int, float)) and control_value != 0:
                change_percent = ((float(value) - float(control_value)) / float(control_value)) * 100.0
            elif isinstance(control_value, (int, float)) and control_value == 0:
                change_percent = 100.0 if value else 0.0
            if change_percent is not None:
                if direction == "higher":
                    vs_control = "better" if change_percent > 0 else ("worse" if change_percent < 0 else "same")
                else:
                    vs_control = "better" if change_percent < 0 else ("worse" if change_percent > 0 else "same")
        change_rounded = round(change_percent, 2) if change_percent is not None else None
        results.append({
            "variant_id": v.get("id"),
            "variant_name": var_name,
            "value": value,
            "vs_control": vs_control,
            "change_percent": change_rounded,
        })
    summaries = []
    for r in results:
        if r.get("vs_control") == "same" or r.get("change_percent") is None:
            s = f"{r.get('variant_name', '')}: без изменения"
        else:
            pct = r.get("change_percent") or 0
            better_worse = "стало лучше" if r.get("vs_control") == "better" else "стало хуже"
            s = f"{r.get('variant_name', '')}: {better_worse} на {abs(pct):.2f}%"
        summaries.append(s)

    recommendation = "keep_control"
    winner_variant_id = None
    winner_variant_name = None
    if direction and results:
        better_results = [r for r in results if r.get("vs_control") == "better"]
        if better_results:
            if direction == "higher":
                best = max(better_results, key=lambda r: (r.get("change_percent") is not None, r.get("change_percent") or 0))
            else:
                best = min(better_results, key=lambda r: (r.get("change_percent") is not None, -(r.get("change_percent") or 0)))
            recommendation = "rollout"
            winner_variant_id = best.get("variant_id")
            if winner_variant_id is not None:
                winner_variant_id = str(winner_variant_id)
            winner_variant_name = best.get("variant_name")

    primary_name = primary_metric_name or primary_metric_key
    return {
        "metric_key": primary_metric_key,
        "metric_name": primary_name,
        "control_value": control_value,
        "control_variant_name": control_variant_name,
        "direction": direction,
        "results": results,
        "summary_lines": summaries,
        "recommendation": recommendation,
        "winner_variant_id": winner_variant_id,
        "winner_variant_name": winner_variant_name,
    }


async def get_experiment_report(experiment: dict, start_iso: str, end_iso: str) -> dict[str, Any]:
    start_ts = _parse_iso(start_iso)
    end_ts = _parse_iso(end_iso)
    variants = experiment["variants"]
    exp_metrics = experiment["metrics"]

    catalog_by_key: dict[str, dict] = {}
    for em in exp_metrics:
        m = await get_metric_by_key(em["metric_key"])
        if m:
            catalog_by_key[em["metric_key"]] = m

    all_event_keys: set[str] = set()
    for em in exp_metrics:
        cat = catalog_by_key.get(em["metric_key"])
        if cat:
            all_event_keys |= _metric_event_type_keys(cat, catalog_by_key)
    event_keys_list = sorted(all_event_keys)

    report_variants = []
    async with Database() as db:
        for v in variants:
            var_id = v.get("id")
            var_name = v.get("variant_name") or ""
            is_control = v.get("is_control") or False
            decision_ids = await _decision_ids_by_variant(db, experiment["id"], var_id)
            metric_values = []
            for em in exp_metrics:
                metric_key = em["metric_key"]
                catalog = catalog_by_key.get(metric_key)
                value = None
                unit = None
                if catalog:
                    value = await _compute_metric_value(db, decision_ids, start_ts, end_ts, catalog)
                    unit = catalog.get("unit")
                metric_values.append({
                    "metric_key": metric_key,
                    "value": value,
                    "unit": unit,
                })
            event_counts = await _event_counts_by_type(db, decision_ids, event_keys_list, start_ts, end_ts)
            report_variants.append({
                "variant_id": var_id,
                "variant_name": var_name,
                "is_control": is_control,
                "metric_values": metric_values,
                "event_counts": event_counts,
            })

    metrics_def = []
    primary_metric_key = None
    primary_metric_name = None
    primary_event_expectations = None
    for em in exp_metrics:
        m = catalog_by_key.get(em["metric_key"])
        metric_type = em.get("metric_type") or ""
        if metric_type == "primary":
            primary_metric_key = em["metric_key"]
            if m:
                primary_metric_name = m.get("name")
                primary_event_expectations = m.get("event_expectations")
        metrics_def.append({
            "metric_key": em["metric_key"],
            "metric_type": metric_type,
            "name": m.get("name") if m else None,
            "unit": m.get("unit") if m else None,
            "event_expectations": m.get("event_expectations") if m else None,
        })

    primary_summary = None
    if primary_metric_key:
        primary_summary = _primary_metric_summary(
            variants, report_variants, primary_metric_key, primary_metric_name, primary_event_expectations
        )

    return {
        "experiment_id": experiment["id"],
        "experiment_name": experiment.get("name"),
        "context": {
            "window_start": start_iso,
            "window_end": end_iso,
            "aggregation_unit": None,
        },
        "metrics": metrics_def,
        "variants": report_variants,
        "primary_metric_summary": primary_summary,
        "dynamics": None,
    }
