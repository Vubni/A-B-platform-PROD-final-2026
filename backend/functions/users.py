"""
Функции для работы с пользователями, ролями и аппрувер-группами.

- users: id, email, first_name, password, verified, role (user_role), created_at, updated_at
- approver_groups: id, experimenter_id (FK users), min_approvals, created_at, updated_at
- approver_group_members: approver_group_id (FK approver_groups), approver_id (FK users)
"""
from typing import Any, Optional
from core import serialize_json, create_token, check_token
from database.database import Database

ROLES = ("admin", "experimenter", "approver", "viewer")



async def get_users_list(role: Optional[str] = None) -> list[dict]:
    async with Database() as db:
        if role:
            rows = await db.execute_all(
                """SELECT id, email, first_name, role, verified, created_at, updated_at
                   FROM users WHERE role = $1""",
                (role,),
            )
        else:
            rows = await db.execute_all(
                """SELECT id, email, first_name, role, verified, created_at, updated_at
                   FROM users"""
            )
        return [serialize_json(r) for r in (rows or [])]


async def create_user(email: str, first_name: str, password: str, role: str = "viewer") -> dict | None:
    async with Database() as db:
        existing = await db.execute(
            "SELECT id FROM users WHERE email = $1 OR first_name = $2",
            (email, first_name),
        )
        if existing:
            return None
        hashed = create_token({"password": password})
        await db.execute(
            """INSERT INTO users (email, first_name, password, role)
               VALUES ($1, $2, $3, $4)""",
            (email, first_name, hashed, role),
        )
        row = await db.execute(
            """SELECT id, email, first_name, role, verified, created_at, updated_at
               FROM users WHERE email = $1""",
            (email,),
        )
        return serialize_json(row)


async def get_user_by_id(user_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT id, email, first_name, role, verified, created_at, updated_at
               FROM users WHERE id = $1""",
            (user_id,),
        )
        return serialize_json(row)


async def get_user_by_email(email: str) -> dict | None:
    async with Database() as db:
        row = await db.execute("SELECT id, email, first_name, role, verified, password, created_at, updated_at FROM users WHERE email = $1", (email,))
        return serialize_json(row)


async def update_user(user_id: str, email: Optional[str] = None, first_name: Optional[str] = None, 
                      password: Optional[str] = None, role: Optional[str] = None) -> dict | None:
    updates: list[str] = []
    params: list[Any] = []
    idx = 1
    if email is not None:
        updates.append(f"email = ${idx}")
        params.append(email)
        idx += 1
    if first_name is not None:
        updates.append(f"first_name = ${idx}")
        params.append(first_name)
        idx += 1
    if password is not None:
        updates.append(f"password = ${idx}")
        params.append(create_token({"password": password}))
        idx += 1
    if role is not None:
        updates.append(f"role = ${idx}")
        params.append(role)
        idx += 1
    if not updates:
        return await get_user_by_id(user_id)

    updates.append("updated_at = NOW()")
    params.append(user_id)

    async with Database() as db:
        exists = await db.execute("SELECT id FROM users WHERE id = $1", (user_id,))
        if not exists:
            return None
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}"
        await db.execute(sql, tuple(params))
    return await get_user_by_id(user_id)


async def get_approver_group_for_experimenter(experimenter_id: str) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            """SELECT ag.id, ag.min_approvals,
                      COALESCE(
                          (SELECT json_agg(agm.approver_id)
                           FROM approver_group_members agm
                           WHERE agm.approver_group_id = ag.id),
                          '[]'::json
                      ) AS approver_ids
               FROM approver_groups ag
               WHERE ag.experimenter_id = $1""",
            (experimenter_id,),)
        if row and (row.get("approver_ids") or []):
            return {
                "min_approvals": row["min_approvals"],
                "approver_ids": row["approver_ids"] or [],
            }
        row = await db.execute(
            """SELECT ag.min_approvals,
                      COALESCE(
                          (SELECT json_agg(agm.approver_id)
                           FROM approver_group_members agm
                           WHERE agm.approver_group_id = ag.id),
                          '[]'::json
                      ) AS approver_ids
               FROM approver_groups ag
               WHERE ag.experimenter_id IS NULL"""
        )
        if row and (row.get("approver_ids") or []):
            return {
                "min_approvals": row["min_approvals"],
                "approver_ids": row["approver_ids"] or [],
            }
        admins = await db.execute_all(
            "SELECT id FROM users WHERE role = 'admin'"
        )
        return {
            "min_approvals": 1,
            "approver_ids": [str(r["id"]) for r in (admins or [])],
        }


async def get_approver_group_by_experimenter(experimenter_id: Optional[str]) -> dict | None:
    """Группа аппруверов по experimenter_id (None — fallback)."""
    async with Database() as db:
        row = await db.execute(
            """SELECT ag.id, ag.experimenter_id, ag.min_approvals,
                      COALESCE(
                          (SELECT json_agg(agm.approver_id)
                           FROM approver_group_members agm
                           WHERE agm.approver_group_id = ag.id),
                          '[]'::json
                      ) AS approver_ids
               FROM approver_groups ag
               WHERE ag.experimenter_id IS NOT DISTINCT FROM $1""",
            (experimenter_id,))
        if not row:
            return None
        return {
            "id": row.get("id"),
            "experimenter_id": row.get("experimenter_id"),
            "min_approvals": row.get("min_approvals"),
            "approver_ids": row.get("approver_ids") or [],
        }


async def get_approver_groups_list() -> list[dict]:
    async with Database() as db:
        rows = await db.execute_all(
            """SELECT ag.id, ag.experimenter_id, ag.min_approvals,
                      COALESCE(
                          (SELECT json_agg(agm.approver_id)
                           FROM approver_group_members agm
                           WHERE agm.approver_group_id = ag.id),
                          '[]'::json
                      ) AS approver_ids
               FROM approver_groups ag"""
        )
        return [
            {
                "id": r.get("id"),
                "experimenter_id": r.get("experimenter_id"),
                "min_approvals": r.get("min_approvals"),
                "approver_ids": r.get("approver_ids") or [],
            }
            for r in (rows or [])
        ]


async def _apply_approver_members(db, group_id: str, approver_ids: list[str]) -> None:
    await db.execute(
        "DELETE FROM approver_group_members WHERE approver_group_id = $1",
        (group_id,),
    )
    for aid in approver_ids:
        approver = await db.execute(
            "SELECT role FROM users WHERE id = $1",
            (aid,),
        )
        if approver and approver.get("role") in ("admin", "approver"):
            await db.execute(
                """INSERT INTO approver_group_members (approver_group_id, approver_id)
                   VALUES ($1, $2)
                   ON CONFLICT (approver_group_id, approver_id) DO NOTHING""",
                (group_id, aid))


async def create_approver_group(experimenter_id: Optional[str], min_approvals: int, approver_ids: list[str]) -> dict | None:
    async with Database() as db:
        if experimenter_id is not None:
            user = await db.execute(
                "SELECT id, role FROM users WHERE id = $1",
                (experimenter_id,))
            if not user:
                return None
        existing = await db.execute(
            "SELECT id FROM approver_groups WHERE experimenter_id IS NOT DISTINCT FROM $1",
            (experimenter_id,))
        if existing:
            return None
        await db.execute("INSERT INTO approver_groups (experimenter_id, min_approvals) VALUES ($1, $2)",
            (experimenter_id, min_approvals))
        row = await db.execute("SELECT id FROM approver_groups WHERE experimenter_id IS NOT DISTINCT FROM $1",
            (experimenter_id,))
        group_id = row["id"] if row else None
        if not group_id:
            return None
        await _apply_approver_members(db, group_id, approver_ids)
        return {
            "id": group_id,
            "experimenter_id": experimenter_id,
            "min_approvals": min_approvals,
            "approver_ids": approver_ids,
        }


async def update_approver_group(group_id: str, min_approvals: Optional[int] = None, approver_ids: Optional[list[str]] = None) -> dict | None:
    async with Database() as db:
        row = await db.execute(
            "SELECT id, experimenter_id, min_approvals FROM approver_groups WHERE id = $1",
            (group_id,),
        )
        if not row:
            return None
        current_min = row["min_approvals"]
        experimenter_id = row["experimenter_id"]
        if min_approvals is not None:
            if min_approvals < 1:
                return None
            await db.execute(
                """UPDATE approver_groups SET min_approvals = $1, updated_at = NOW()
                   WHERE id = $2""",
                (min_approvals, group_id),
            )
            current_min = min_approvals
        if approver_ids is not None:
            await _apply_approver_members(db, group_id, approver_ids)
        else:
            members = await db.execute_all(
                "SELECT approver_id FROM approver_group_members WHERE approver_group_id = $1",
                (group_id,),
            )
            approver_ids = [r["approver_id"] for r in (members or [])]
        return {
            "id": group_id,
            "experimenter_id": experimenter_id,
            "min_approvals": current_min,
            "approver_ids": approver_ids,
        }