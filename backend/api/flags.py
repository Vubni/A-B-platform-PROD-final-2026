from typing import Any, Optional

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from core import check_authorization, FLAG_KEY_PATTERN
from docs.schems import FlagCreateSchema, FlagUpdateSchema, FlagItemSchema, FlagListResponseSchema
from functions.flags import (
    FLAG_VALUE_TYPES,
    create_flag,
    get_flag_by_key,
    get_flags_list,
    update_flag_default_value,
)
from api import validate


def _validate_default_value_by_type(value_type: str, default_value: str) -> None:
    if value_type == "string":
        return
    if value_type == "number":
        try:
            if "." in default_value:
                float(default_value)
            else:
                int(default_value)
        except ValueError:
            raise ValueError(
                "default_value must be a valid number for value_type=number")
        return
    if value_type == "bool":
        if default_value.lower() not in ("true", "false", "1", "0", "yes", "no"):
            raise ValueError(
                "default_value for value_type=bool must be one of: true, false, 1, 0, yes, no")
        return
    raise ValueError(f"value_type must be one of {FLAG_VALUE_TYPES}")


class FlagCreate(BaseModel):
    key: str
    value_type: str
    default_value: str
    description: Optional[str] = None
    owner: Optional[str] = None
    metadata: Optional[dict] = None

    @field_validator("key")
    @classmethod
    def key_format(cls, v: str) -> str:
        if not v or len(v) > 255:
            raise ValueError("key must be non-empty and up to 255 characters")
        if not FLAG_KEY_PATTERN.match(v):
            raise ValueError(
                "key must start with a letter and contain only letters, digits and underscore")
        return v

    @field_validator("value_type")
    @classmethod
    def value_type_one_of(cls, v: str) -> str:
        if v not in FLAG_VALUE_TYPES:
            raise ValueError(f"value_type must be one of {FLAG_VALUE_TYPES}")
        return v

    @field_validator("default_value", mode="before")
    @classmethod
    def default_value_valid(cls, v, info) -> str:
        if v is None:
            raise ValueError("default_value is required")
        if isinstance(v, (int, float)):
            v = str(v)
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("default_value is required")
        v = v.strip() if isinstance(v, str) else str(v)
        value_type = info.data.get("value_type") if hasattr(info, "data") else None
        if value_type:
            _validate_default_value_by_type(value_type, v)
        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def metadata_dict(cls, v: Any) -> Optional[dict]:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        raise ValueError("metadata must be a dictionary")


class FlagUpdate(BaseModel):
    default_value: str

    @field_validator("default_value")
    @classmethod
    def default_value_non_empty(cls, v: str) -> str:
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("default_value is required")
        return v.strip() if isinstance(v, str) else str(v)


@docs(
    tags=["Feature Flags"],
    summary="Создать feature flag",
    description="Создание нового feature flag с ключом, типом значения и значением по умолчанию.",
    responses={
        201: {"description": "Флаг создан", "schema": FlagItemSchema},
        400: {"description": "Некорректный запрос"},
        409: {"description": "Флаг с таким ключом уже существует"},
    },
)
@request_schema(FlagCreateSchema(), location="json", put_into="data")
@validate.validate(FlagCreate)
async def flags_create(request: web.Request, parsed: FlagCreate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] not in ("admin", "experimenter"):
        return validate.format_403_error(request, "Not enough permissions to create flags")

    flag = await create_flag(
        key=parsed.key,
        value_type=parsed.value_type,
        default_value=parsed.default_value,
        description=parsed.description,
        owner=parsed.owner,
        metadata=parsed.metadata,
    )
    if not flag:
        return validate.format_409_error(request, parsed.key, "Flag with this key already exists", field="key")
    return web.json_response(flag, status=201)


@docs(
    tags=["Feature Flags"],
    summary="Список feature flags",
    description="Получить список всех feature flags",
    responses={200: {"description": "Список флагов", "schema": FlagListResponseSchema}},
)
async def flags_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    flags_data = await get_flags_list()
    return web.json_response({"flags": flags_data})


@docs(
    tags=["Feature Flags"],
    summary="Получить feature flag",
    description="Получить feature flag по ключу.",
    responses={
        200: {"description": "Данные флага", "schema": FlagItemSchema},
        404: {"description": "Флаг не найден"},
    },
)
async def flags_get(request: web.Request) -> web.Response:
    key = request.match_info.get("key", "").strip()
    if not key:
        return web.json_response({"error": "Missing flag key"}, status=400)

    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    flag = await get_flag_by_key(key)
    if not flag:
        return validate.format_404_error(request, "Flag not found")
    return web.json_response(flag)


@docs(
    tags=["Feature Flags"],
    summary="Обновить значение по умолчанию feature flag",
    description="Обновить только значение по умолчанию существующего флага. Варианты и эксперименты не меняются.",
    responses={
        200: {"description": "Флаг обновлён", "schema": FlagItemSchema},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Флаг не найден"},
    },
)
@request_schema(FlagUpdateSchema(), location="json", put_into="data")
@validate.validate(FlagUpdate)
async def flags_update(request: web.Request, parsed: FlagUpdate) -> web.Response:
    key = request.match_info.get("key", "").strip()
    if not key:
        return web.json_response({"error": "Missing flag key"}, status=400)

    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] not in ("admin", "experimenter"):
        return validate.format_403_error(request, "Not enough permissions to update flags")

    flag = await get_flag_by_key(key)
    if not flag:
        return validate.format_404_error(request, "Flag not found")

    value_type = flag.get("value_type", "string")
    try:
        _validate_default_value_by_type(value_type, parsed.default_value)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)

    updated = await update_flag_default_value(key, parsed.default_value)
    if not updated:
        return validate.format_404_error(request, "Flag not found")
    return web.json_response(updated)
