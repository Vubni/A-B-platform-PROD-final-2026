import json
import uuid
from typing import Optional

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from core import parse_uuid, validate_uuid
from core import check_authorization
from docs.schems import (
    UserCreateSchema,
    UserUpdateSchema,
    UserListQuerySchema,
    ApproverGroupSetSchema,
    ApproverGroupUpdateSchema,
)
from functions.users import (
    ROLES,
    create_approver_group,
    create_user,
    get_approver_group_by_experimenter,
    get_approver_groups_list,
    get_user_by_id,
    get_users_list,
    update_approver_group,
    update_user,
)
from api import validate


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
    experimenter_id: Optional[str] = None
    min_approvals: int = 1
    approver_ids: list[str] = []

    @field_validator("experimenter_id")
    @classmethod
    def experimenter_id_uuid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_uuid(v)

    @field_validator("approver_ids", mode="before")
    @classmethod
    def approver_ids_uuids(cls, v):
        if not v:
            return []
        return [validate_uuid(str(x)) for x in v]


class ApproverGroupUpdate(BaseModel):
    min_approvals: Optional[int] = None
    approver_ids: Optional[list[str]] = None

    @field_validator("approver_ids", mode="before")
    @classmethod
    def approver_ids_uuids(cls, v):
        if v is None:
            return None
        if not v:
            return []
        return [validate_uuid(str(x)) for x in v]


class UserList(BaseModel):
    role: Optional[str] = None



@docs(
    tags=["Users"],
    summary="Список пользователей",
    description=(
        "Список пользователей с опциональным фильтром по роли. "
        "Доступ: Admin — все пользователи."
    ),
    responses={200: {"description": "Список пользователей (массив в поле users)"}},
)
@request_schema(UserListQuerySchema(), location="querystring", put_into="querystring")
@validate.validate(UserList)
async def users_list(request: web.Request, parsed: UserList) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "admin":
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    users_data = await get_users_list(parsed.role)
    return web.json_response({"users": users_data})


@docs(
    tags=["Users"],
    summary="Создать пользователя",
    description="Создать пользователя и назначить роль. Доступ: Admin.",
    responses={
        201: {"description": "Пользователь создан (объект пользователя без пароля)"},
        400: {"description": "Некорректный запрос"},
        409: {"description": "Email или first_name уже заняты"},
    },
)
@request_schema(UserCreateSchema(), location="json", put_into="data")
@validate.validate(UserCreate)
async def users_create(request: web.Request, parsed: UserCreate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "admin":
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    user = await create_user(
        email=parsed.email,
        first_name=parsed.first_name,
        password=parsed.password,
        role=parsed.role,
    )
    if not user:
        return validate.format_409_error(request, "User with such email or first_name already exists")
    return web.json_response(user, status=201)


@docs(
    tags=["Users"],
    summary="Получить пользователя",
    description="Получить пользователя по ID. Path: id — UUID пользователя.",
    responses={
        200: {"description": "Данные пользователя (id, email, first_name, role, verified, created_at, updated_at)"},
        404: {"description": "Пользователь не найден"},
    },
)
async def users_get(request: web.Request) -> web.Response:
    user_id = parse_uuid(request.match_info.get("id", ""))
    if not user_id:
        return web.json_response({"error": "Invalid user id (expected UUID)"}, status=400)

    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "admin" and auth_payload["id"] != user_id:
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    user = await get_user_by_id(user_id)
    if not user:
        return validate.format_404_error(request, "User not found")
    return web.json_response(user)


@docs(
    tags=["Users"],
    summary="Обновить пользователя",
    description="Обновить пользователя и/или назначить роль. Доступ: Admin. Path: id — UUID пользователя.",
    responses={
        200: {"description": "Пользователь обновлён (объект пользователя без пароля)"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Пользователь не найден"},
    },
)
@request_schema(UserUpdateSchema(), location="json", put_into="data")
@validate.validate(UserUpdate)
async def users_update(request: web.Request, parsed: UserUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "admin":
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    user_id = parse_uuid(request.match_info.get("id", ""))
    if not user_id:
        return web.json_response({"error": "Invalid user id (expected UUID)"}, status=400)

    if not (parsed.email or parsed.first_name or parsed.password or parsed.role):
        return web.json_response({"error": "No fields to update"}, status=400)
    user = await update_user(user_id, parsed.email, parsed.first_name, parsed.password, parsed.role)
    if not user:
        return validate.format_404_error(request, "User not found")
    return web.json_response(user)


@docs(
    tags=["Users"],
    summary="Список групп аппруверов",
    description=(
        "Список групп одобряющих. experimenter_id=null — fallback-группа. "
        "Для Experimenter без персональной группы используется fallback, "
        "а при её отсутствии — min_approvals=1, approver_ids=все admin."
    ),
    responses={200: {"description": "Список групп аппруверов (поле approver_groups)"}},
)
async def approver_groups_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] not in ["admin", "approver", "experimenter", "viewer"]:
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    groups = await get_approver_groups_list()
    return web.json_response({"approver_groups": groups})


@docs(
    tags=["Users"],
    summary="Создать группу аппруверов",
    description=(
        "Создать новую группу. experimenter_id=null — fallback-группа (единственная). "
        "Если группа для experimenter_id уже есть — 409. "
        "Доступ: Admin. В группу попадают только пользователи с role admin/approver."
    ),
    responses={
        201: {"description": "Группа создана (объект группы с id, experimenter_id, min_approvals, created_at, updated_at)"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Experimenter не найден"},
        409: {"description": "Группа для experimenter_id уже существует"},
    },
)
@request_schema(ApproverGroupSetSchema(), location="json", put_into="data")
@validate.validate(ApproverGroupSet)
async def approver_groups_create(request: web.Request, parsed: ApproverGroupSet) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "approver":
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    if parsed.min_approvals < 1:
        return web.json_response({"error": "min_approvals must be >= 1"}, status=400)
    result = await create_approver_group(
        experimenter_id=parsed.experimenter_id,
        min_approvals=parsed.min_approvals,
        approver_ids=parsed.approver_ids,
    )
    if not result:
        existing = await get_approver_group_by_experimenter(parsed.experimenter_id)
        if existing:
            return validate.format_409_error(request, "Approver group for this experimenter_id already exists")
        return validate.format_404_error(request, "Experimenter not found or database error")
    return web.json_response(result, status=201)


@docs(
    tags=["Users"],
    summary="Обновить группу аппруверов",
    description=(
        "Обновить min_approvals и/или список approver_ids по id группы. "
        "Доступ: Admin. Path: id — UUID группы."
    ),
    responses={
        200: {"description": "Группа обновлена (объект группы)"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Группа не найдена"},
    },
)
@request_schema(ApproverGroupUpdateSchema(), location="json", put_into="data")
@validate.validate(ApproverGroupUpdate)
async def approver_groups_update(request: web.Request, parsed: ApproverGroupUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "approver":
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    group_id = parse_uuid(request.match_info.get("id", ""))
    if not group_id:
        return web.json_response({"error": "Invalid group id (expected UUID)"}, status=400)

    if parsed.min_approvals is not None and parsed.min_approvals < 1:
        return web.json_response({"error": "min_approvals must be >= 1"}, status=400)
    if parsed.min_approvals is None and parsed.approver_ids is None:
        return web.json_response({"error": "No fields to update"}, status=400)
    result = await update_approver_group(
        group_id,
        min_approvals=parsed.min_approvals,
        approver_ids=parsed.approver_ids,
    )
    if not result:
        return validate.format_404_error(request, "Approver group not found")
    return web.json_response(result)
