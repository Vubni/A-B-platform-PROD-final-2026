import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from typing import Any


def _stable_score(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest, 16)


def _stable_ratio(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    value = int(digest, 16)
    return value / float(0xFFFFFFFFFFFFFFFF)


def _pick_winner_for_domain(
    subject_id: str,
    domain_key: str,
    config_version: int,
    policy: str,
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if policy == "priority":
        max_tier = max(int(c.get("priority_tier") or 0) for c in candidates)
        top = [c for c in candidates if int(c.get("priority_tier") or 0) == max_tier]
        winner = max(
            top,
            key=lambda c: _stable_score(
                f"{subject_id}|{domain_key}|{config_version}|priority|{c['experiment_id']}"
            ),
        )
    elif policy == "bid":
        weighted = [
            (c, Decimal(str(c.get("bid_value") or 0)))
            for c in sorted(candidates, key=lambda x: str(x["experiment_id"]))
        ]
        total = sum(w for _, w in weighted)
        if total <= 0:
            winner = max(
                candidates,
                key=lambda c: _stable_score(
                    f"{subject_id}|{domain_key}|{config_version}|bid-fallback|{c['experiment_id']}"
                ),
            )
        else:
            ratio = Decimal(str(_stable_ratio(f"{subject_id}|{domain_key}|{config_version}|bid")))
            cutoff = ratio * total
            cursor = Decimal("0")
            winner = weighted[-1][0]
            for candidate, weight in weighted:
                cursor += weight
                if cutoff <= cursor:
                    winner = candidate
                    break
    else:
        winner = max(
            candidates,
            key=lambda c: _stable_score(
                f"{subject_id}|{domain_key}|{config_version}|mutual|{c['experiment_id']}"
            ),
        )
    losers = [c for c in candidates if c["experiment_id"] != winner["experiment_id"]]
    return winner, losers


def _resolve_domain_conflicts(
    subject_id: str,
    domains: list[dict[str, Any]],
) -> tuple[set[str], list[dict[str, Any]], dict[str, str]]:
    all_experiment_ids = {
        str(candidate["experiment_id"]) for domain in domains for candidate in domain["candidates"]
    }
    allowed = set(all_experiment_ids)
    blocked_by_domain: dict[str, str] = {}
    logs: list[dict[str, Any]] = []

    for domain in sorted(domains, key=lambda d: d["domain_key"]):
        active_candidates = [c for c in domain["candidates"] if str(c["experiment_id"]) in allowed]
        if len(active_candidates) <= 1:
            continue
        winner, losers = _pick_winner_for_domain(
            subject_id=subject_id,
            domain_key=domain["domain_key"],
            config_version=int(domain["config_version"]),
            policy=domain["policy"],
            candidates=active_candidates,
        )
        loser_ids = {str(c["experiment_id"]) for c in losers}
        for loser_id in loser_ids:
            blocked_by_domain[loser_id] = domain["domain_key"]
        allowed -= loser_ids
        logs.append(
            {
                "domain_id": str(domain["domain_id"]),
                "domain_key": domain["domain_key"],
                "policy_used": domain["policy"],
                "config_version": int(domain["config_version"]),
                "winner_experiment_id": str(winner["experiment_id"]),
                "candidates": [
                    {
                        "experiment_id": str(c["experiment_id"]),
                        "priority_tier": c.get("priority_tier"),
                        "bid_value": float(c.get("bid_value") or 0),
                    }
                    for c in active_candidates
                ],
                "losers": [
                    {
                        "experiment_id": str(c["experiment_id"]),
                        "priority_tier": c.get("priority_tier"),
                        "bid_value": float(c.get("bid_value") or 0),
                    }
                    for c in losers
                ],
            }
        )

    return allowed, logs, blocked_by_domain


async def resolve_experiment_conflicts(
    db,
    subject_id: str,
    experiments: list[dict[str, Any]],
) -> tuple[set[str], list[dict[str, Any]], dict[str, str]]:
    experiment_ids = [str(e["id"]) for e in experiments]
    all_requested_ids = set(experiment_ids)
    if not experiment_ids:
        return set(), [], {}

    rows = await db.execute_all(
        """SELECT ecb.experiment_id,
                  cd.id AS domain_id,
                  cd.key AS domain_key,
                  cd.config_version,
                  COALESCE(ecb.policy::text, cd.default_policy::text) AS policy,
                  ecb.priority_tier,
                  ecb.bid_value
           FROM experiment_conflict_bindings ecb
           JOIN conflict_domains cd ON cd.id = ecb.domain_id
           WHERE ecb.is_enabled = TRUE
             AND ecb.experiment_id = ANY($1::uuid[])""",
        (experiment_ids,),
    )
    if not rows:
        return all_requested_ids, [], {}

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta_by_domain: dict[str, dict[str, Any]] = {}
    for row in rows:
        domain_key = str(row["domain_key"])
        grouped[domain_key].append(
            {
                "experiment_id": str(row["experiment_id"]),
                "priority_tier": row.get("priority_tier"),
                "bid_value": row.get("bid_value"),
            }
        )
        if domain_key not in meta_by_domain:
            meta_by_domain[domain_key] = {
                "domain_id": str(row["domain_id"]),
                "domain_key": domain_key,
                "config_version": int(row["config_version"]),
                "policy": str(row["policy"]),
            }

    domains = [
        {
            **meta_by_domain[domain_key],
            "candidates": candidates,
        }
        for domain_key, candidates in grouped.items()
    ]
    allowed_bound, logs, blocked_by_domain = _resolve_domain_conflicts(
        subject_id=subject_id, domains=domains
    )
    bound_ids = {
        str(candidate["experiment_id"]) for domain in domains for candidate in domain["candidates"]
    }
    unbound_ids = all_requested_ids - bound_ids
    return allowed_bound | unbound_ids, logs, blocked_by_domain


async def store_conflict_logs(db, subject_id: str, logs: list[dict[str, Any]]) -> None:
    for item in logs:
        await db.execute(
            """INSERT INTO decision_conflict_log
                   (subject_id, domain_id, policy_used, config_version,
                    winner_experiment_id, candidates, losers)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            (
                subject_id,
                item["domain_id"],
                item["policy_used"],
                item["config_version"],
                item["winner_experiment_id"],
                json.dumps(item["candidates"]),
                json.dumps(item["losers"]),
            ),
        )


async def get_preflight_conflicts(db, experiment_id: str) -> list[dict[str, Any]]:
    """Список доменов, в которых запуск этого эксперимента создаст конфликт с уже running."""
    rows = await db.execute_all(
        """SELECT cd.id AS domain_id, cd.key AS domain_key, cd.name AS domain_name,
                  e2.id AS conflicting_id, e2.name AS conflicting_name, f.key AS flag_key
           FROM experiment_conflict_bindings ecb
           JOIN conflict_domains cd ON cd.id = ecb.domain_id AND ecb.is_enabled = TRUE
           JOIN experiment_conflict_bindings ecb2
             ON ecb2.domain_id = cd.id AND ecb2.experiment_id != $1 AND ecb2.is_enabled = TRUE
           JOIN experiments e2 ON e2.id = ecb2.experiment_id AND e2.status IN ('running', 'paused')
           JOIN feature_flags f ON f.id = e2.flag_id
           WHERE ecb.experiment_id = $1""",
        (experiment_id,),
    )
    if not rows:
        return []
    by_domain: dict[str, dict[str, Any]] = {}
    for r in rows:
        dk = str(r["domain_key"])
        if dk not in by_domain:
            by_domain[dk] = {
                "domain_id": str(r["domain_id"]),
                "domain_key": dk,
                "domain_name": r.get("domain_name") or dk,
                "conflicting_experiments": [],
            }
        by_domain[dk]["conflicting_experiments"].append(
            {
                "experiment_id": str(r["conflicting_id"]),
                "experiment_name": r.get("conflicting_name") or "",
                "flag_key": r.get("flag_key") or "",
            }
        )
    return list(by_domain.values())


POLICY_TYPES = ("mutual_exclusion", "bid", "priority")


async def list_domains(db) -> list[dict[str, Any]]:
    rows = await db.execute_all(
        """SELECT id, key, name, description, default_policy::text, config_version,
                  created_at, updated_at FROM conflict_domains ORDER BY key"""
    )
    return [_row_to_domain(r) for r in (rows or [])]


async def get_domain_by_id(db, domain_id: str) -> dict[str, Any] | None:
    row = await db.execute(
        """SELECT id, key, name, description, default_policy::text, config_version,
                  created_at, updated_at FROM conflict_domains WHERE id = $1""",
        (domain_id,),
    )
    return _row_to_domain(row) if row else None


async def get_domain_by_key(db, key: str) -> dict[str, Any] | None:
    row = await db.execute(
        """SELECT id, key, name, description, default_policy::text, config_version,
                  created_at, updated_at FROM conflict_domains WHERE key = $1""",
        (key,),
    )
    return _row_to_domain(row) if row else None


def _row_to_domain(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "key": row["key"],
        "name": row["name"],
        "description": row.get("description"),
        "default_policy": row.get("default_policy") or "mutual_exclusion",
        "config_version": int(row.get("config_version") or 1),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def create_domain(
    db,
    key: str,
    name: str,
    description: str | None = None,
    default_policy: str = "mutual_exclusion",
) -> dict[str, Any] | None:
    if default_policy not in POLICY_TYPES:
        return None
    key = (key or "").strip()
    name = (name or "").strip()
    if not key or not name:
        return None
    await db.execute(
        """INSERT INTO conflict_domains (key, name, description, default_policy)
           VALUES ($1, $2, $3, $4::conflict_policy_type)""",
        (key, name, description, default_policy),
    )
    return await get_domain_by_key(db, key)


async def update_domain(
    db,
    domain_id: str,
    name: str | None = None,
    description: str | None = None,
    default_policy: str | None = None,
) -> dict[str, Any] | None:
    updates = ["updated_at = NOW()"]
    params: list[Any] = []
    idx = 1
    if name is not None:
        updates.append(f"name = ${idx}")
        params.append((name or "").strip())
        idx += 1
    if description is not None:
        updates.append(f"description = ${idx}")
        params.append(description)
        idx += 1
    if default_policy is not None:
        if default_policy not in POLICY_TYPES:
            return None
        updates.append(f"default_policy = ${idx}::conflict_policy_type")
        params.append(default_policy)
        idx += 1
        updates.append("config_version = config_version + 1")
    if len(params) == 0:
        return await get_domain_by_id(db, domain_id)
    params.append(domain_id)
    await db.execute(
        f"UPDATE conflict_domains SET {', '.join(updates)} WHERE id = ${idx}",
        tuple(params),
    )
    return await get_domain_by_id(db, domain_id)


async def delete_domain(db, domain_id: str) -> bool:
    existing = await db.execute(
        "SELECT 1 FROM conflict_domains WHERE id = $1",
        (domain_id,),
    )
    if not existing:
        return False
    await db.execute(
        "DELETE FROM conflict_domains WHERE id = $1",
        (domain_id,),
    )
    return True


async def list_bindings_for_experiment(db, experiment_id: str) -> list[dict[str, Any]]:
    rows = await db.execute_all(
        """SELECT ecb.experiment_id, ecb.domain_id, cd.key AS domain_key, cd.name AS domain_name,
                  ecb.policy::text AS policy, ecb.priority_tier, ecb.bid_value, ecb.is_enabled,
                  ecb.created_at, ecb.updated_at
           FROM experiment_conflict_bindings ecb
           JOIN conflict_domains cd ON cd.id = ecb.domain_id
           WHERE ecb.experiment_id = $1 ORDER BY cd.key""",
        (experiment_id,),
    )
    return [_row_to_binding(r) for r in (rows or [])]


async def list_bindings_for_domain(db, domain_id: str) -> list[dict[str, Any]]:
    rows = await db.execute_all(
        """SELECT ecb.experiment_id, ecb.domain_id, cd.key AS domain_key, cd.name AS domain_name,
                  ecb.policy::text AS policy, ecb.priority_tier, ecb.bid_value, ecb.is_enabled,
                  e.name AS experiment_name, e.status::text AS experiment_status,
                  ecb.created_at, ecb.updated_at
           FROM experiment_conflict_bindings ecb
           JOIN conflict_domains cd ON cd.id = ecb.domain_id
           JOIN experiments e ON e.id = ecb.experiment_id
           WHERE ecb.domain_id = $1 ORDER BY e.name""",
        (domain_id,),
    )
    out = []
    for r in rows or []:
        b = _row_to_binding(r)
        b["experiment_name"] = r.get("experiment_name")
        b["experiment_status"] = r.get("experiment_status")
        out.append(b)
    return out


def _row_to_binding(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": str(row["experiment_id"]),
        "domain_id": str(row["domain_id"]),
        "domain_key": row.get("domain_key"),
        "domain_name": row.get("domain_name"),
        "policy": row.get("policy"),
        "priority_tier": row.get("priority_tier"),
        "bid_value": float(row.get("bid_value") or 0),
        "is_enabled": bool(row.get("is_enabled", True)),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def upsert_binding(
    db,
    experiment_id: str,
    domain_id: str,
    policy: str | None = None,
    priority_tier: int | None = None,
    bid_value: float = 0,
    is_enabled: bool = True,
) -> dict[str, Any] | None:
    if policy is not None and policy not in POLICY_TYPES:
        return None
    await db.execute(
        """INSERT INTO experiment_conflict_bindings
                   (experiment_id, domain_id, policy, priority_tier, bid_value, is_enabled)
           VALUES ($1, $2, $3::conflict_policy_type, $4, $5, $6)
           ON CONFLICT (experiment_id, domain_id)
           DO UPDATE SET policy = COALESCE(EXCLUDED.policy, experiment_conflict_bindings.policy),
                         priority_tier = COALESCE(EXCLUDED.priority_tier, experiment_conflict_bindings.priority_tier),
                         bid_value = COALESCE(EXCLUDED.bid_value, experiment_conflict_bindings.bid_value),
                         is_enabled = EXCLUDED.is_enabled,
                         updated_at = NOW()""",
        (
            experiment_id,
            domain_id,
            policy,
            priority_tier,
            bid_value,
            is_enabled,
        ),
    )
    row = await db.execute(
        """SELECT ecb.experiment_id, ecb.domain_id, cd.key AS domain_key, cd.name AS domain_name,
                  ecb.policy::text, ecb.priority_tier, ecb.bid_value, ecb.is_enabled,
                  ecb.created_at, ecb.updated_at
           FROM experiment_conflict_bindings ecb
           JOIN conflict_domains cd ON cd.id = ecb.domain_id
           WHERE ecb.experiment_id = $1 AND ecb.domain_id = $2""",
        (experiment_id, domain_id),
    )
    return _row_to_binding(row) if row else None


async def delete_binding(db, experiment_id: str, domain_id: str) -> bool:
    existing = await db.execute(
        """SELECT 1 FROM experiment_conflict_bindings
           WHERE experiment_id = $1 AND domain_id = $2""",
        (experiment_id, domain_id),
    )
    if not existing:
        return False
    await db.execute(
        """DELETE FROM experiment_conflict_bindings
           WHERE experiment_id = $1 AND domain_id = $2""",
        (experiment_id, domain_id),
    )
    return True


async def get_conflict_log_for_experiment(
    db, experiment_id: str, limit: int = 100
) -> list[dict[str, Any]]:
    """Записи, где эксперимент был победителем или проигравшим."""
    rows = await db.execute_all(
        """SELECT dcl.id, dcl.subject_id, dcl.domain_id, cd.key AS domain_key,
                  dcl.policy_used, dcl.config_version, dcl.winner_experiment_id,
                  dcl.candidates, dcl.losers, dcl.created_at
           FROM decision_conflict_log dcl
           JOIN conflict_domains cd ON cd.id = dcl.domain_id
           WHERE dcl.winner_experiment_id = $1
              OR (dcl.losers::jsonb @> $2::jsonb)
           ORDER BY dcl.created_at DESC LIMIT $3""",
        (experiment_id, json.dumps([{"experiment_id": experiment_id}]), limit),
    )
    out = []
    for r in rows or []:
        out.append(
            {
                "id": str(r["id"]),
                "subject_id": r["subject_id"],
                "domain_id": str(r["domain_id"]),
                "domain_key": r.get("domain_key"),
                "policy_used": r.get("policy_used"),
                "winner_experiment_id": str(r["winner_experiment_id"]),
                "candidates": r.get("candidates"),
                "losers": r.get("losers"),
                "created_at": r.get("created_at"),
                "won": str(r["winner_experiment_id"]) == str(experiment_id),
            }
        )
    return out


async def get_conflict_stats_for_report(
    db, experiment_id: str, start_ts: Any, end_ts: Any
) -> dict[str, Any]:
    """Агрегаты по decision_conflict_log за окно: раз выиграл конфликт, раз проиграл."""
    won_row = await db.execute(
        """SELECT COUNT(*) AS cnt FROM decision_conflict_log
           WHERE winner_experiment_id = $1 AND created_at >= $2 AND created_at < $3""",
        (experiment_id, start_ts, end_ts),
    )
    lost_row = await db.execute(
        """SELECT COUNT(*) AS cnt FROM decision_conflict_log
           WHERE losers::jsonb @> $1::jsonb AND created_at >= $2 AND created_at < $3""",
        (json.dumps([{"experiment_id": experiment_id}]), start_ts, end_ts),
    )
    return {
        "times_winner": int((won_row or {}).get("cnt") or 0),
        "times_loser": int((lost_row or {}).get("cnt") or 0),
    }
