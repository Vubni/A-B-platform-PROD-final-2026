"""Users, roles, approver groups. Обработчики HTTP — вызывают functions.users."""
import json
from typing import Optional

from aiohttp import web
from aiohttp_apispec import docs
from pydantic import BaseModel, field_validator

from functions.users import (
    ROLES,
    create_user,
    get_approver_groups_list,
    get_user_by_id,
    get_users_list,
    set_approver_group,
    update_user,
)


class UserCreate(BaseModel):
    email: str
    first_name: str
    password: str
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v


class UserUpdate(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ROLES:
            raise ValueError(f"role must be one of {ROLES}")
        return v


class ApproverGroupSet(BaseModel):
    experimenter_id: Optional[int] = None
    min_approvals: int = 1
    approver_ids: list[int] = []


@docs(
    tags=["Users"],
    summary="Список пользователей",
    description=(
        "Список пользователей с опциональным фильтром по роли. "
        "Доступ: Admin — все пользователи; Viewer — только чтение."
    ),
    responses={200: {"description": "Список пользователей"}},
)
async def users_list(request: web.Request) -> web.Response:
    role = request.query.get("role")
    if role and role not in ROLES:
        return web.json_response({"error": f"Invalid role. Must be one of {ROLES}"}, status=400)
    users_data = await get_users_list(role=role)
    return web.json_response({"users": users_data})


@docs(
    tags=["Users"],
    summary="Создать пользователя",
    description="Создать пользователя и назначить роль. Доступ: Admin.",
    responses={
        201: {"description": "Пользователь создан"},
        400: {"description": "Некорректный запрос"},
        409: {"description": "Email или first_name уже заняты"},
    },
)
async def users_create(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    try:
        parsed = UserCreate(**data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)
    user = await create_user(
        email=parsed.email,
        first_name=parsed.first_name,
        password=parsed.password,
        role=parsed.role,
    )
    if not user:
        return web.json_response(
            {"error": "User with such email or first_name already exists"},
            status=409,
        )
    return web.json_response(user, status=201)


@docs(
    tags=["Users"],
    summary="Получить пользователя",
    description="Получить пользователя по ID.",
    responses={
        200: {"description": "Данные пользователя"},
        404: {"description": "Пользователь не найден"},
    },
)
async def users_get(request: web.Request) -> web.Response:
    try:
        user_id = int(request.match_info["id"])
    except ValueError:
        return web.json_response({"error": "Invalid user id"}, status=400)
    user = await get_user_by_id(user_id)
    if not user:
        return web.json_response({"error": "User not found"}, status=404)
    return web.json_response(user)


@docs(
    tags=["Users"],
    summary="Обновить пользователя",
    description="Обновить пользователя и/или назначить роль. Доступ: Admin.",
    responses={
        200: {"description": "Пользователь обновлён"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Пользователь не найден"},
    },
)
async def users_update(request: web.Request) -> web.Response:
    try:
        user_id = int(request.match_info["id"])
    except ValueError:
        return web.json_response({"error": "Invalid user id"}, status=400)
    try:
        data = await request.json()
    except json.JSONDecodeError:
        data = {}
    try:
        parsed = UserUpdate(**data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)
    updates = {}
    if parsed.email is not None:
        updates["email"] = parsed.email
    if parsed.first_name is not None:
        updates["first_name"] = parsed.first_name
    if parsed.password is not None:
        updates["password"] = parsed.password
    if parsed.role is not None:
        updates["role"] = parsed.role
    if not updates:
        return web.json_response({"error": "No fields to update"}, status=400)
    user = await update_user(user_id, **updates)
    if not user:
        return web.json_response({"error": "User not found"}, status=404)
    return web.json_response(user)


@docs(
    tags=["Users"],
    summary="Список групп аппруверов",
    description=(
        "Список групп одобряющих. experimenter_id=null — fallback-группа. "
        "Для Experimenter без персональной группы используется fallback, "
        "а при её отсутствии — min_approvals=1, approver_ids=все admin."
    ),
    responses={200: {"description": "Список групп аппруверов"}},
)
async def approver_groups_list(request: web.Request) -> web.Response:
    groups = await get_approver_groups_list()
    return web.json_response({"approver_groups": groups})


@docs(
    tags=["Users"],
    summary="Создать/обновить группу аппруверов",
    description=(
        "Настроить аппруверов для Experimenter и min_approvals. "
        "experimenter_id=null — fallback-группа (единственная). "
        "Доступ: Admin. В группу попадают только пользователи с role admin/approver."
    ),
    responses={
        200: {"description": "Группа настроена"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Experimenter не найден"},
    },
)
async def approver_groups_set(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    try:
        parsed = ApproverGroupSet(**data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)
    if parsed.min_approvals < 1:
        return web.json_response({"error": "min_approvals must be >= 1"}, status=400)
    result = await set_approver_group(
        experimenter_id=parsed.experimenter_id,
        min_approvals=parsed.min_approvals,
        approver_ids=parsed.approver_ids,
    )
    if not result:
        return web.json_response(
            {"error": "Experimenter not found or database error"},
            status=404,
        )
    return web.json_response({**result, "status": "ok"})
