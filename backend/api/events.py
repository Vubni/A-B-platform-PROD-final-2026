from typing import Optional, Any

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from core import check_authorization, validate_uuid
from api import validate
from api.system_metrics import record_events_submitted
from docs.schems import (
    EventsSubmitRequestSchema,
    EventsSubmitResponseSchema,
    EventTypesListQuerySchema,
    EventTypesListResponseSchema,
    EventTypeItemSchema,
    EventTypeCreateSchema,
    EventTypeUpdateSchema,
)
from functions.event_types import (
    list_event_types,
    get_event_type_by_id,
    create_event_type,
    update_event_type,
    archive_event_type,
)
from functions.events_submit import process_events_batch

from typing import List

class EventsSubmitInput(BaseModel):
    events: List[dict]

class EventTypeCreate(BaseModel):
    key: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    required_params: Optional[dict] = None
    validation_type: Optional[str] = None
    report_alert_config: Optional[dict] = None
    requires_show_event_type_id: Optional[str] = None
    is_critical: bool = False

    @field_validator("key")
    @classmethod
    def key_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("key is required")
        return v.strip()

    @field_validator("requires_show_event_type_id")
    @classmethod
    def requires_show_uuid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        u = validate_uuid(v)
        if not u:
            raise ValueError("requires_show_event_type_id must be a valid UUID")
        return u


class EventTypeUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    required_params: Optional[dict] = None
    validation_type: Optional[str] = None
    report_alert_config: Optional[dict] = None
    requires_show_event_type_id: Optional[str] = None
    is_critical: Optional[bool] = None

    @field_validator("requires_show_event_type_id")
    @classmethod
    def requires_show_uuid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        u = validate_uuid(v)
        if not u:
            raise ValueError("requires_show_event_type_id must be a valid UUID")
        return u


def _event_type_id_from_request(request: web.Request) -> Optional[str]:
    raw = request.match_info.get("id", "").strip()
    if not raw:
        return None
    return validate_uuid(raw)


@docs(
    tags=["Events"],
    summary="Отправить пакет событий",
    description=(
        "Принять пакет событий от продукта. Каждое событие связано с decision_id. "
        "Возвращает: количество принятых, дубликатов, отклонённых и ошибки по отклонённым."
    ),
    responses={
        200: {"description": "Пакет обработан. См. счётчики accepted/duplicates/rejected.", "schema": EventsSubmitResponseSchema},
        400: {"description": "Некорректный формат пакета"},
    },
)
@request_schema(EventsSubmitRequestSchema(), location="json", put_into="data")
@validate.validate(EventsSubmitInput)
async def events_submit(request: web.Request, parsed: EventsSubmitInput) -> web.Response:
    result = await process_events_batch(parsed.events)
    record_events_submitted(accepted=result["accepted"])
    return web.json_response(
        {
            "accepted": result["accepted"],
            "duplicates": result["duplicates"],
            "rejected": result["rejected"],
            "errors": result["errors"],
            "status": "ok",
        },
        status=200,
    )


@docs(
    tags=["Events"],
    summary="Список типов событий (каталог)",
    description="Получить каталог типов событий. Админ создаёт/редактирует типы с метаданными и правилами валидации.",
    responses={
        200: {"description": "Список типов событий", "schema": EventTypesListResponseSchema},
        401: {"description": "Требуется авторизация"},
    },
)
@request_schema(EventTypesListQuerySchema(), location="querystring", put_into="querystring")
async def event_types_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    status = request.query.get("status", "").strip() or None
    if status and status not in ("active", "archived"):
        status = None
    items = await list_event_types(status=status)
    return web.json_response({"event_types": items})


@docs(
    tags=["Events"],
    summary="Создать тип события",
    description="Создать тип события в каталоге (Админ).",
    responses={
        201: {"description": "Тип события создан", "schema": EventTypeItemSchema},
        400: {"description": "Некорректный запрос"},
        403: {"description": "Только для админа"},
        409: {"description": "Тип с таким key уже существует"},
    },
)
@request_schema(EventTypeCreateSchema(), location="json", put_into="data")
@validate.validate(EventTypeCreate)
async def event_types_create(request: web.Request, parsed: EventTypeCreate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "admin":
        return validate.format_403_error(request, "Only admin can create event types")
    data, err = await create_event_type(
        key=parsed.key,
        display_name=parsed.display_name,
        description=parsed.description,
        required_params=parsed.required_params,
        validation_type=parsed.validation_type,
        report_alert_config=parsed.report_alert_config,
        requires_show_event_type_id=parsed.requires_show_event_type_id,
        is_critical=parsed.is_critical)
    if err == "duplicate_key":
        return validate.format_409_error(request, parsed.key, "Event type with this key already exists", field="key")
    if err == "db_error":
        return web.json_response(
            validate.format_error_response(
                code="INTERNAL_ERROR",
                message="Failed to load created event type",
                path=str(request.path_qs),
                status=500,
            ),
            status=500,
        )
    if err == "invalid_requires_show":
        return web.json_response(
            validate.format_error_response(
                code="BAD_REQUEST",
                message="requires_show_event_type_id must reference an existing active event type",
                path=str(request.path_qs),
                status=400,
                details={"field": "requires_show_event_type_id"},
            ),
            status=400)
    return web.json_response(data, status=201)


@docs(
    tags=["Events"],
    summary="Получить тип события",
    description="Получить тип события по id.",
    responses={
        200: {"description": "Данные типа события", "schema": EventTypeItemSchema},
        401: {"description": "Требуется авторизация"},
        404: {"description": "Не найден"},
    },
)
async def event_types_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    type_id = _event_type_id_from_request(request)
    if not type_id:
        return validate.format_404_error(request, "Invalid event type id")
    item = await get_event_type_by_id(type_id)
    if not item:
        return validate.format_404_error(request, "Event type not found")
    return web.json_response(item)


@docs(
    tags=["Events"],
    summary="Обновить тип события",
    description="Обновить тип события (Админ).",
    responses={
        200: {"description": "Обновлено", "schema": EventTypeItemSchema},
        400: {"description": "Некорректный запрос (например самозависимость или неверный requires_show)"},
        401: {"description": "Требуется авторизация"},
        403: {"description": "Только для админа"},
        404: {"description": "Не найден"},
    },
)
@request_schema(EventTypeUpdateSchema(), location="json", put_into="data")
@validate.validate(EventTypeUpdate)
async def event_types_update(request: web.Request, parsed: EventTypeUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "admin":
        return validate.format_403_error(request, "Only admin can update event types")
    type_id = _event_type_id_from_request(request)
    if not type_id:
        return validate.format_404_error(request, "Invalid event type id")
    data, err = await update_event_type(
        type_id,
        display_name=parsed.display_name,
        description=parsed.description,
        required_params=parsed.required_params,
        validation_type=parsed.validation_type,
        report_alert_config=parsed.report_alert_config,
        requires_show_event_type_id=parsed.requires_show_event_type_id,
        is_critical=parsed.is_critical)
    if err == "not_found":
        return validate.format_404_error(request, "Event type not found")
    if err == "self_reference":
        return web.json_response(
            validate.format_error_response(
                code="BAD_REQUEST",
                message="requires_show_event_type_id cannot reference the same event type",
                path=str(request.path_qs),
                status=400,
                details={"field": "requires_show_event_type_id"},
            ),
            status=400)
    if err == "invalid_requires_show":
        return web.json_response(
            validate.format_error_response(
                code="BAD_REQUEST",
                message="requires_show_event_type_id must reference an existing active event type",
                path=str(request.path_qs),
                status=400,
                details={"field": "requires_show_event_type_id"},
            ),
            status=400)
    return web.json_response(data)


@docs(
    tags=["Events"],
    summary="Архивировать тип события",
    description="Архивировать тип события (мягкое удаление).",
    responses={
        200: {"description": "Архивировано", "schema": EventTypeItemSchema},
        401: {"description": "Требуется авторизация"},
        403: {"description": "Только для админа"},
        404: {"description": "Не найден"},
    },
)
async def event_types_archive(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "admin":
        return validate.format_403_error(request, "Only admin can archive event types")
    type_id = _event_type_id_from_request(request)
    if not type_id:
        return validate.format_404_error(request, "Invalid event type id")
    item = await archive_event_type(type_id)
    if not item:
        return validate.format_404_error(request, "Event type not found")
    return web.json_response(item)
