import json
import re

from core import serialize_json
from database.database import Database

LEARNING_OUTCOMES = ("rollout_winner", "rollback", "no_effect", "worse")
LEARNING_ACTIONS = ("rollout", "rollback", "continue", "repeat")


def _jaccard(a: list[str] | None, b: list[str] | None) -> float:
    sa = {x.strip().lower() for x in (a or []) if isinstance(x, str) and x.strip()}
    sb = {x.strip().lower() for x in (b or []) if isinstance(x, str) and x.strip()}
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _tokenize_text(value: str | None) -> list[str]:
    if not value:
        return []
    return re.findall(r"[a-zA-Z0-9_]{2,}", value.lower())


def _text_jaccard(a: str | None, b: str | None) -> float:
    return _jaccard(_tokenize_text(a), _tokenize_text(b))


def _variant_structure_similarity(a: dict | None, b: dict | None) -> float:
    sa = a or {}
    sb = b or {}
    if not sa and not sb:
        return 0.0
    if sa == sb:
        return 1.0
    keys_a = [str(k) for k in sa.keys()]
    keys_b = [str(k) for k in sb.keys()]
    return _jaccard(keys_a, keys_b)


def _score_similarity(base: dict, candidate: dict) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if base.get("flag_key") == candidate.get("flag_key"):
        score += 0.35
        reasons.append("same_flag_key")
    if base.get("primary_metric_key") == candidate.get("primary_metric_key"):
        score += 0.10
        reasons.append("same_primary_metric")
    if (base.get("change_type") or "") == (candidate.get("change_type") or "") and base.get(
        "change_type"
    ):
        score += 0.05
        reasons.append("same_change_type")
    if (base.get("result_outcome") or "") == (candidate.get("result_outcome") or "") and base.get(
        "result_outcome"
    ):
        score += 0.05
        reasons.append("same_result_outcome")

    tags_overlap = _jaccard(base.get("product_tags"), candidate.get("product_tags"))
    if tags_overlap > 0:
        reasons.append("overlap_product_tags")
    score += tags_overlap * 0.18

    platforms_overlap = _jaccard(base.get("platforms"), candidate.get("platforms"))
    if platforms_overlap > 0:
        reasons.append("overlap_platforms")
    score += platforms_overlap * 0.08

    countries_overlap = _jaccard(base.get("countries"), candidate.get("countries"))
    if countries_overlap > 0:
        reasons.append("overlap_countries")
    score += countries_overlap * 0.08

    app_versions_overlap = _jaccard(base.get("app_versions"), candidate.get("app_versions"))
    if app_versions_overlap > 0:
        reasons.append("overlap_app_versions")
    score += app_versions_overlap * 0.04

    guardrails_overlap = _jaccard(base.get("guardrail_metric_keys"), candidate.get("guardrail_metric_keys"))
    if guardrails_overlap > 0:
        reasons.append("overlap_guardrail_metrics")
    score += guardrails_overlap * 0.04

    targeting_similarity = _text_jaccard(base.get("targeting_summary"), candidate.get("targeting_summary"))
    if targeting_similarity > 0:
        reasons.append("similar_targeting_summary")
    score += targeting_similarity * 0.04

    variant_similarity = _variant_structure_similarity(
        base.get("variant_structure"), candidate.get("variant_structure")
    )
    if variant_similarity > 0:
        reasons.append("similar_variant_structure")
    score += variant_similarity * 0.04

    return round(min(score, 1.0), 5), reasons


async def _get_learning_by_id_using_db(db: Database, learning_id: str) -> dict | None:
    row = await db.execute(
        """
        SELECT l.*,
               e.name AS experiment_name,
               e.status::text AS experiment_status
        FROM experiment_learnings l
        JOIN experiments e ON e.id = l.experiment_id
        WHERE l.id = $1
        """,
        (learning_id,))
    if not row:
        return None

    guardrails = await db.execute_all(
        """
        SELECT id, learning_id, metric_key, threshold_value, trigger_count, details, created_at
        FROM learning_guardrails
        WHERE learning_id = $1
        ORDER BY metric_key ASC
        """,
        (learning_id,))
    row["guardrails"] = guardrails or []
    row["guardrail_metric_keys"] = [g.get("metric_key") for g in (guardrails or []) if g.get("metric_key")]
    return serialize_json(row)


async def get_learning_by_id(learning_id: str) -> dict | None:
    async with Database() as db:
        return await _get_learning_by_id_using_db(db, learning_id)


async def get_learning_by_experiment_id(experiment_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            "SELECT id FROM experiment_learnings WHERE experiment_id = $1",
            (experiment_id,))
        if not row:
            return None
        return await _get_learning_by_id_using_db(db, str(row["id"]))


async def upsert_learning(
    experiment_id: str,
    flag_key: str,
    owner_user_id: str | None,
    owner_team: str | None,
    hypothesis: str,
    primary_metric_key: str,
    result_outcome: str,
    result_action: str,
    effect_summary: str | None,
    targeting_summary: str | None,
    platforms: list[str] | None,
    countries: list[str] | None,
    app_versions: list[str] | None,
    product_tags: list[str] | None,
    change_type: str | None,
    variant_structure: dict | None,
    report_url: str | None,
    ticket_url: str | None,
    notes: str,
    is_completed: bool,
    guardrails: list[dict] | None,
    actor_user_id: str | None,
) -> dict | None:
    async with Database() as db:
        guardrail_triggers_count = sum(int((g or {}).get("trigger_count") or 0) for g in (guardrails or []))
        learning_id = await db.fetchval(
            """
            INSERT INTO experiment_learnings (
                experiment_id, flag_key, owner_user_id, owner_team, hypothesis, primary_metric_key,
                result_outcome, result_action, effect_summary, guardrail_triggers_count, targeting_summary, platforms, countries,
                app_versions, product_tags, change_type, variant_structure, report_url, ticket_url,
                notes, is_completed, created_by, updated_by
            )
            VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17, $18, $19,
                $20, $21, $22, $23
            )
            ON CONFLICT (experiment_id)
            DO UPDATE SET
                flag_key = EXCLUDED.flag_key,
                owner_user_id = EXCLUDED.owner_user_id,
                owner_team = EXCLUDED.owner_team,
                hypothesis = EXCLUDED.hypothesis,
                primary_metric_key = EXCLUDED.primary_metric_key,
                result_outcome = EXCLUDED.result_outcome,
                result_action = EXCLUDED.result_action,
                effect_summary = EXCLUDED.effect_summary,
                guardrail_triggers_count = EXCLUDED.guardrail_triggers_count,
                targeting_summary = EXCLUDED.targeting_summary,
                platforms = EXCLUDED.platforms,
                countries = EXCLUDED.countries,
                app_versions = EXCLUDED.app_versions,
                product_tags = EXCLUDED.product_tags,
                change_type = EXCLUDED.change_type,
                variant_structure = EXCLUDED.variant_structure,
                report_url = EXCLUDED.report_url,
                ticket_url = EXCLUDED.ticket_url,
                notes = EXCLUDED.notes,
                is_completed = EXCLUDED.is_completed,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            RETURNING id
            """,
            (
                experiment_id,
                flag_key,
                owner_user_id,
                owner_team,
                hypothesis,
                primary_metric_key,
                result_outcome,
                result_action,
                effect_summary,
                guardrail_triggers_count,
                targeting_summary,
                platforms or [],
                countries or [],
                app_versions or [],
                product_tags or [],
                change_type,
                json.dumps(variant_structure or {}),
                report_url,
                ticket_url,
                notes,
                is_completed,
                actor_user_id,
                actor_user_id,
            ))
        if not learning_id:
            return None
        learning_id = str(learning_id)

        await db.execute("DELETE FROM learning_guardrails WHERE learning_id = $1", (learning_id,))
        for g in guardrails or []:
            await db.execute(
                """
                INSERT INTO learning_guardrails (learning_id, metric_key, threshold_value, trigger_count, details)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (learning_id, metric_key)
                DO UPDATE SET
                    threshold_value = EXCLUDED.threshold_value,
                    trigger_count = EXCLUDED.trigger_count,
                    details = EXCLUDED.details
                """,
                (
                    learning_id,
                    g.get("metric_key"),
                    g.get("threshold_value"),
                    int(g.get("trigger_count") or 0),
                    json.dumps(g.get("details") or {}),
                ))
        return await _get_learning_by_id_using_db(db, learning_id)


async def list_learnings(
    q: str | None = None,
    flag_key: str | None = None,
    owner_user_id: str | None = None,
    owner_team: str | None = None,
    result_outcome: str | None = None,
    primary_metric_key: str | None = None,
    countries: list[str] | None = None,
    platforms: list[str] | None = None,
    tags: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    async with Database() as db:
        sql = """
            SELECT l.id, l.experiment_id, l.flag_key, l.owner_user_id, l.owner_team, l.hypothesis,
                   l.primary_metric_key, l.result_outcome, l.result_action, l.effect_summary,
                   l.guardrail_triggers_count, l.targeting_summary, l.platforms, l.countries,
                   l.app_versions, l.product_tags, l.change_type, l.variant_structure,
                   l.report_url, l.ticket_url, l.notes, l.is_completed, l.created_by, l.updated_by,
                   l.created_at, l.updated_at,
                   e.name AS experiment_name, e.status::text AS experiment_status
            FROM experiment_learnings l
            JOIN experiments e ON e.id = l.experiment_id
            WHERE 1=1
        """
        params: list = []
        idx = 1

        if q:
            sql += f" AND l.search_document @@ plainto_tsquery('simple', ${idx})"
            params.append(q)
            idx += 1
        if flag_key:
            sql += f" AND l.flag_key = ${idx}"
            params.append(flag_key)
            idx += 1
        if owner_user_id:
            sql += f" AND l.owner_user_id = ${idx}"
            params.append(owner_user_id)
            idx += 1
        if owner_team:
            sql += f" AND l.owner_team = ${idx}"
            params.append(owner_team)
            idx += 1
        if result_outcome:
            sql += f" AND l.result_outcome = ${idx}"
            params.append(result_outcome)
            idx += 1
        if primary_metric_key:
            sql += f" AND l.primary_metric_key = ${idx}"
            params.append(primary_metric_key)
            idx += 1
        if countries:
            sql += f" AND l.countries && ${idx}::text[]"
            params.append(countries)
            idx += 1
        if platforms:
            sql += f" AND l.platforms && ${idx}::text[]"
            params.append(platforms)
            idx += 1
        if tags:
            sql += f" AND l.product_tags && ${idx}::text[]"
            params.append(tags)
            idx += 1
        if date_from:
            sql += f" AND l.created_at >= ${idx}::timestamptz"
            params.append(date_from)
            idx += 1
        if date_to:
            sql += f" AND l.created_at <= ${idx}::timestamptz"
            params.append(date_to)
            idx += 1

        sql += f" ORDER BY l.updated_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])

        rows = await db.execute_all(sql, tuple(params))
        return serialize_json(rows)


async def list_learning_audit(learning_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """
            SELECT id, learning_id, action, changed_by, changed_at, before_state, after_state
            FROM experiment_learning_audit_log
            WHERE learning_id = $1
            ORDER BY changed_at DESC
            LIMIT $2 OFFSET $3
            """,
            (learning_id, limit, offset))
        guardrail_rows = []
        try:
            guardrail_rows = await db.execute_all(
                """
                SELECT id, learning_id, action, changed_by, changed_at, before_state, after_state
                FROM learning_guardrails_audit_log
                WHERE learning_id = $1
                ORDER BY changed_at DESC
                """,
                (learning_id,),
            )
        except Exception:
            guardrail_rows = []
        combined = (rows or []) + (guardrail_rows or [])
        combined.sort(key=lambda x: str(x.get("changed_at") or ""), reverse=True)
        paged = combined[offset : offset + limit]
        return serialize_json(paged)


async def find_similar_learnings(learning_id: str, limit: int = 5) -> list[dict]:
    async with Database() as db:
        base = await _get_learning_by_id_using_db(db, learning_id)
        if not base:
            return []

        candidates = await db.execute_all(
            """
            SELECT l.id, l.experiment_id, l.flag_key, l.owner_user_id, l.owner_team, l.hypothesis,
                   l.primary_metric_key, l.result_outcome, l.result_action, l.effect_summary,
                   l.guardrail_triggers_count, l.targeting_summary, l.platforms, l.countries,
                   l.app_versions, l.product_tags, l.change_type, l.variant_structure,
                   l.report_url, l.ticket_url, l.notes, l.is_completed, l.created_by, l.updated_by,
                   l.created_at, l.updated_at,
                   e.name AS experiment_name, e.status::text AS experiment_status
            FROM experiment_learnings l
            JOIN experiments e ON e.id = l.experiment_id
            WHERE l.id <> $1
            """,
            (learning_id,))
        if not candidates:
            return []

        all_guardrails = await db.execute_all(
            """
            SELECT learning_id, metric_key
            FROM learning_guardrails
            WHERE learning_id = ANY($1::uuid[])
            """,
            ([learning_id] + [str(c["id"]) for c in candidates],))
        guardrails_map: dict[str, list[str]] = {}
        for r in all_guardrails or []:
            lid = str(r["learning_id"])
            guardrails_map.setdefault(lid, []).append(r["metric_key"])
        base["guardrail_metric_keys"] = guardrails_map.get(learning_id, [])

        enriched = []
        for c in candidates:
            cid = str(c["id"])
            c["guardrail_metric_keys"] = guardrails_map.get(cid, [])
            score, reasons = _score_similarity(base, c)
            if score <= 0:
                continue
            enriched.append(
                {
                    "score": score,
                    "reasons": reasons,
                    "learning": serialize_json(c),
                }
            )

            await db.execute(
                """
                INSERT INTO learning_similarity_cache (
                    learning_id, similar_learning_id, score, computed_at, algorithm_version
                )
                VALUES ($1, $2, $3, NOW(), 'v1')
                ON CONFLICT (learning_id, similar_learning_id)
                DO UPDATE SET score = EXCLUDED.score, computed_at = NOW(), algorithm_version = 'v1'
                """,
                (learning_id, cid, score))

        enriched.sort(key=lambda x: x["score"], reverse=True)
        return enriched[:limit]
