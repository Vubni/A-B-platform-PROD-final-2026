from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from api.system_metrics import record_events_submitted
from config import EVENTS_USE_KAFKA, KAFKA_BOOTSTRAP_SERVERS
from core import check_authorization, validate_uuid
from docs.schems import (
    RESPONSES_HTTP_ERROR,
    EventsSubmitRequestSchema,
    EventsSubmitResponseSchema,
    EventTypeCreateSchema,
    EventTypeItemSchema,
    EventTypesListQuerySchema,
    EventTypesListResponseSchema,
    EventTypeUpdateSchema,
)
from functions.event_types import (
    archive_event_type,
    create_event_type,
    get_event_type_by_id,
    list_event_types,
    update_event_type,
)
from functions.events_submit import process_events_batch, validate_events_batch


class EventsSubmitInput(BaseModel):
    events: list[dict]

    @field_validator("events")
    @classmethod
    def events_bounded(cls, v: list) -> list:
        if not isinstance(v, list):
            raise ValueError("events must be a list")
        if len(v) > 10_000:
            raise ValueError("events list cannot exceed 10000 items")
        return v


class EventTypeCreate(BaseModel):
    key: str
    display_name: str | None = None
    description: str | None = None
    required_params: dict | None = None
    validation_type: str | None = None
    report_alert_config: dict | None = None
    requires_show_event_type_id: str | None = None
    is_critical: bool = False

    @field_validator("key")
    @classmethod
    def key_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("key is required")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("key must be at most 255 characters")
        return v

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError("display_name must be at most 255 characters")
        return v

    @field_validator("description")
    @classmethod
    def description_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 2048:
            raise ValueError("description must be at most 2048 characters")
        return v

    @field_validator("requires_show_event_type_id")
    @classmethod
    def requires_show_uuid(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        u = validate_uuid(v)
        if not u:
            raise ValueError("requires_show_event_type_id must be a valid UUID")
        return u


class EventTypeUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    required_params: dict | None = None
    validation_type: str | None = None
    report_alert_config: dict | None = None
    requires_show_event_type_id: str | None = None
    is_critical: bool | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError("display_name must be at most 255 characters")
        return v

    @field_validator("description")
    @classmethod
    def description_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 2048:
            raise ValueError("description must be at most 2048 characters")
        return v

    @field_validator("requires_show_event_type_id")
    @classmethod
    def requires_show_uuid(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        u = validate_uuid(v)
        if not u:
            raise ValueError("requires_show_event_type_id must be a valid UUID")
        return u


def _event_type_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    if not raw:
        return None
    return validate_uuid(raw)



def _kafka_consumer_ready(app: web.Application) -> bool:
    task = app.get("kafka_consumer_task")
    return task is not None and not task.done()

@docs(
    tags=["Events"],
    summary="Отправить пакет событий",
    responses={
        200: {"schema": EventsSubmitResponseSchema},
        202: {},
        400: RESPONSES_HTTP_ERROR[400],
        422: RESPONSES_HTTP_ERROR[422],
    },
)
@request_schema(EventsSubmitRequestSchema(), location="json", put_into="data")
@validate.validate(EventsSubmitInput)
async def events_submit(request: web.Request, parsed: EventsSubmitInput) -> web.Response:
    if EVENTS_USE_KAFKA and KAFKA_BOOTSTRAP_SERVERS:
        pre = await validate_events_batch(parsed.events)
        if pre["rejected"] > 0:
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
        if not _kafka_consumer_ready(request.app):
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
        from kafka_events import produce_events_batch

        await produce_events_batch(parsed.events)
        record_events_submitted(accepted=len(parsed.events))
        return web.json_response(
            {"status": "accepted", "message": "events queued for processing"},
            status=202,
        )
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
    summary="Список типов событий",
    responses={
        200: {"schema": EventTypesListResponseSchema},
        401: RESPONSES_HTTP_ERROR[401],
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
    responses={
        201: {"schema": EventTypeItemSchema},
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        409: RESPONSES_HTTP_ERROR[409],
        422: RESPONSES_HTTP_ERROR[422],
        500: RESPONSES_HTTP_ERROR[500],
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
        is_critical=parsed.is_critical,
    )
    if err == "duplicate_key":
        return validate.format_409_error(
            request, parsed.key, "Event type with this key already exists", field="key"
        )
    if err == "db_error":
        return validate.format_500_error(request, "Failed to load created event type")
    if err == "invalid_requires_show":
        return validate.format_400_error(
            request,
            "requires_show_event_type_id must reference an existing active event type",
            details={"field": "requires_show_event_type_id"},
        )
    return web.json_response(data, status=201)


@docs(
    tags=["Events"],
    summary="Получить тип события",
    responses={
        200: {"schema": EventTypeItemSchema},
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
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
    responses={
        200: {"schema": EventTypeItemSchema},
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
        422: RESPONSES_HTTP_ERROR[422],
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
        is_critical=parsed.is_critical,
    )
    if err == "not_found":
        return validate.format_404_error(request, "Event type not found")
    if err == "self_reference":
        return validate.format_400_error(
            request,
            "requires_show_event_type_id cannot reference the same event type",
            details={"field": "requires_show_event_type_id"},
        )
    if err == "invalid_requires_show":
        return validate.format_400_error(
            request,
            "requires_show_event_type_id must reference an existing active event type",
            details={"field": "requires_show_event_type_id"},
        )
    return web.json_response(data)


@docs(
    tags=["Events"],
    summary="Архивировать тип события",
    responses={
        200: {"schema": EventTypeItemSchema},
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
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
