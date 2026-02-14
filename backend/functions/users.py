"""
Функции для работы с пользователями, ролями и аппрувер-группами.

- users: id, email, first_name, password, verified, role (user_role), created_at, updated_at
- approver_groups: id, experimenter_id (FK users), min_approvals, created_at, updated_at
- approver_group_members: approver_group_id (FK approver_groups), approver_id (FK users)

Роли (user_role): admin, experimenter, approver, viewer
"""
import hashlib
import secrets
from typing import Any, Optional

from database.database import Database

ROLES = ("admin", "experimenter", "approver", "viewer")


def _hash_password(password: str) -> str:
    """Хеширование пароля с солью (SHA-256 + salt)."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def _verify_password(plain: str, stored: str) -> bool:
    """Проверка пароля по сохранённому хешу."""
    if not stored or "$" not in stored:
        return False
    salt, hash_part = stored.split("$", 1)
    h = hashlib.sha256((salt + plain).encode()).hexdigest()
    return h == hash_part


def _user_row_to_dict(row: dict | None) -> dict:
    """Сериализация строки users без пароля."""
    if not row:
        return {}
    return {
        "id": row.get("id"),
        "email": row.get("email"),
        "first_name": row.get("first_name"),
        "role": row.get("role"),
        "verified": row.get("verified"),
        "created_at": str(row.get("created_at")) if row.get("created_at") else None,
        "updated_at": str(row.get("updated_at")) if row.get("updated_at") else None,
    }


async def get_users_list(role: Optional[str] = None) -> list[dict]:
    """
    Список пользователей с опциональным фильтром по роли.

    PostgreSQL:
        SELECT id, email, first_name, role, verified, created_at, updated_at
        FROM users
        [WHERE role = $1]
    """
    async with Database() as db:
        if not db:
            return []
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
        return [_user_row_to_dict(r) for r in (rows or [])]


async def create_user(
    email: str,
    first_name: str,
    password: str,
    role: str = "viewer",
) -> dict | None:
    """
    Создание пользователя.

    PostgreSQL:
        INSERT INTO users (email, first_name, password, role)
        VALUES ($1, $2, $3, $4)
        -- проверка: SELECT FROM users WHERE email = $1 OR first_name = $2
    """
    async with Database() as db:
        if not db:
            return None
        existing = await db.execute(
            "SELECT id FROM users WHERE email = $1 OR first_name = $2",
            (email, first_name),
        )
        if existing:
            return None  # conflict
        hashed = _hash_password(password)
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
        return _user_row_to_dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    """
    Получение пользователя по ID.

    PostgreSQL:
        SELECT id, email, first_name, role, verified, created_at, updated_at
        FROM users WHERE id = $1
    """
    async with Database() as db:
        if not db:
            return None
        row = await db.execute(
            """SELECT id, email, first_name, role, verified, created_at, updated_at
               FROM users WHERE id = $1""",
            (user_id,),
        )
        return _user_row_to_dict(row) if row else None


async def update_user(
    user_id: int,
    *,
    email: Optional[str] = None,
    first_name: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[str] = None,
) -> dict | None:
    """
    Обновление пользователя. Только переданные поля меняются.

    PostgreSQL:
        UPDATE users SET col1 = $1, ..., updated_at = NOW() WHERE id = $n
        SELECT ... FROM users WHERE id = $1
    """
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
        params.append(_hash_password(password))
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
        if not db:
            return None
        exists = await db.execute("SELECT id FROM users WHERE id = $1", (user_id,))
        if not exists:
            return None
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx}"
        await db.execute(sql, tuple(params))
        return await get_user_by_id(user_id)


async def get_approver_group_for_experimenter(experimenter_id: int) -> dict | None:
    """
    Группа аппруверов для Experimenter с fallback.

    Fallback (если у experimenter нет своей группы):
    1. Группа с experimenter_id = $1
    2. Fallback-группа (experimenter_id IS NULL) — единая для всех без персональной
    3. Если fallback-группы нет или она пуста: min_approvals=1, approver_ids = все admin

    PostgreSQL:
        SELECT ag.id, ag.min_approvals, json_agg(agm.approver_id)
        FROM approver_groups ag
        LEFT JOIN approver_group_members agm ON agm.approver_group_id = ag.id
        WHERE ag.experimenter_id = $1 OR ag.experimenter_id IS NULL
    """
    async with Database() as db:
        if not db:
            return None
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
            (experimenter_id,),
        )
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
            "approver_ids": [r["id"] for r in (admins or [])],
        }


async def get_approver_groups_list() -> list[dict]:
    """
    Список всех аппрувер-групп (персональные + fallback).

    PostgreSQL:
        SELECT ag.id, ag.experimenter_id, ag.min_approvals,
               json_agg(agm.approver_id)
        FROM approver_groups ag
        LEFT JOIN approver_group_members agm ON agm.approver_group_id = ag.id
        GROUP BY ag.id
    """
    async with Database() as db:
        if not db:
            return []
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


async def set_approver_group(
    experimenter_id: Optional[int],
    min_approvals: int,
    approver_ids: list[int],
) -> dict | None:
    """
    Создание/обновление аппрувер-группы.
    experimenter_id=None — fallback-группа (одна на всю систему).
    Approver_id должны быть пользователями с role IN ('admin','approver').

    PostgreSQL:
        approver_groups: UPSERT по experimenter_id (UNIQUE)
        approver_group_members: DELETE старые, INSERT новые
    """
    if min_approvals < 1:
        return None
    async with Database() as db:
        if not db:
            return None
        if experimenter_id is not None:
            user = await db.execute(
                "SELECT id, role FROM users WHERE id = $1",
                (experimenter_id,),
            )
            if not user:
                return None
        existing = await db.execute(
            "SELECT id FROM approver_groups WHERE experimenter_id IS NOT DISTINCT FROM $1",
            (experimenter_id,),
        )
        if existing:
            group_id = existing["id"]
            await db.execute(
                """UPDATE approver_groups SET min_approvals = $1, updated_at = NOW()
                   WHERE id = $2""",
                (min_approvals, group_id),
            )
        else:
            await db.execute(
                """INSERT INTO approver_groups (experimenter_id, min_approvals)
                   VALUES ($1, $2)""",
                (experimenter_id, min_approvals),
            )
            row = await db.execute(
                """SELECT id FROM approver_groups
                   WHERE experimenter_id IS NOT DISTINCT FROM $1""",
                (experimenter_id,),
            )
            group_id = row["id"] if row else None
        if not group_id:
            return None
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
                    (group_id, aid),
                )
        return {
            "id": group_id,
            "experimenter_id": experimenter_id,
            "min_approvals": min_approvals,
            "approver_ids": approver_ids,
        }
