from datetime import datetime

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator, model_validator

from api import validate
from api.system_metrics import record_report_requested
from core import check_authorization, validate_uuid
from docs.schems import (
    MetricCatalogCreateSchema,
    MetricCatalogItemSchema,
    MetricCatalogUpdateSchema,
    MetricsListResponseSchema,
    ReportExperimentResponseSchema,
)
from functions.experiments import get_experiment_by_id
from functions.metrics import create_metric, get_metric_by_key, list_metrics, update_metric
from functions.reports import get_experiment_report


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    if not raw:
        return None
    return raw if validate_uuid(raw) else None


def _metric_key_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("key", "").strip()
    if not raw:
        return None
    return raw


def _parse_iso_for_validate(s: str) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


class ReportsExperiment(BaseModel):
    start: str
    end: str

    @field_validator("start")
    @classmethod
    def start_iso(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("start is required")
        return v.strip()

    @field_validator("end")
    @classmethod
    def end_iso(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("end is required")
        return v.strip()

    @model_validator(mode="after")
    def check_window(self) -> "ReportsExperiment":
        start_ts = _parse_iso_for_validate(self.start)
        end_ts = _parse_iso_for_validate(self.end)
        if not start_ts or not end_ts or start_ts >= end_ts:
            raise ValueError("invalid_window")
        return self


class MetricsCreate(BaseModel):
    key: str
    name: str
    aggregation_rule: dict
    description: str | None = None
    attribution_rule: dict | None = None
    event_expectations: dict | None = None
    unit: str | None = None

    @field_validator("key")
    @classmethod
    def key_nonempty(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("key is required")
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("key must be non-empty and at most 255 characters")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("key must contain only letters, digits and underscore")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name is required")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("name must be at most 255 characters")
        return v

    @field_validator("aggregation_rule")
    @classmethod
    def aggregation_rule_valid(cls, v: dict) -> dict:
        if not v or not isinstance(v, dict):
            raise ValueError("aggregation_rule is required and must be an object")
        return v

    @field_validator("description")
    @classmethod
    def description_optional(cls, v: str | None) -> str | None:
        if v is not None:
            if not isinstance(v, str) or len(v) > 2048:
                raise ValueError("description must be a string and less than 2048 characters")
        return v

    @field_validator("attribution_rule")
    @classmethod
    def attribution_rule_optional(cls, v: dict | None) -> dict | None:
        if v is not None and not isinstance(v, dict):
            raise ValueError("attribution_rule must be an object")
        return v

    @field_validator("event_expectations")
    @classmethod
    def event_expectations_optional(cls, v: dict | None) -> dict | None:
        if v is not None and not isinstance(v, dict):
            raise ValueError("event_expectations must be an object")
        return v

    @field_validator("unit")
    @classmethod
    def unit_optional(cls, v: str | None) -> str | None:
        if v is not None and not isinstance(v, str):
            raise ValueError("unit must be a string")
        if v is not None and len(v) > 64:
            raise ValueError("unit must be at most 64 characters")
        return v.strip() if isinstance(v, str) else v


class MetricsUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    aggregation_rule: dict | None = None
    attribution_rule: dict | None = None
    event_expectations: dict | None = None
    unit: str | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("name must be non-empty and at most 255 characters")
        return v

    @field_validator("description")
    @classmethod
    def description_valid(cls, v: str | None) -> str | None:
        if v is not None and isinstance(v, str) and len(v) > 2048:
            raise ValueError("description must be at most 2048 characters")
        return v

    @field_validator("aggregation_rule")
    @classmethod
    def aggregation_rule_valid(cls, v: dict | None) -> dict | None:
        if v is not None and not isinstance(v, dict):
            raise ValueError("aggregation_rule must be an object")
        return v

    @field_validator("attribution_rule")
    @classmethod
    def attribution_rule_valid(cls, v: dict | None) -> dict | None:
        if v is not None and not isinstance(v, dict):
            raise ValueError("attribution_rule must be an object")
        return v

    @field_validator("event_expectations")
    @classmethod
    def event_expectations_valid(cls, v: dict | None) -> dict | None:
        if v is not None and not isinstance(v, dict):
            raise ValueError("event_expectations must be an object")
        return v

    @field_validator("unit")
    @classmethod
    def unit_valid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("unit must be a string")
        if len(v) > 64:
            raise ValueError("unit must be at most 64 characters")
        return v.strip()


@docs(
    tags=["Reports"],
    summary="Отчёт по эксперименту",
    description=(
        "Сводный отчёт по эксперименту для оценки эффекта вариантов на целевые метрики. "
        "Метрики считаются в заданном временном окне: от start (включительно) до end (не включительно). "
        "Для каждого варианта возвращаются значения выбранных метрик (основная, дополнительные, guardrail), "
        "контекст расчёта (окно, атрибуция, единица агрегации). "
        "События атрибутируются к эксперименту/варианту через идентификатор решения (decision_id)."
    ),
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "type": "string",
            "format": "uuid",
        },
        {
            "name": "start",
            "in": "query",
            "required": True,
            "description": "Начало окна отчёта (ISO 8601), включительно",
            "type": "string",
        },
        {
            "name": "end",
            "in": "query",
            "required": True,
            "description": "Конец окна отчёта (ISO 8601), не включительно",
            "type": "string",
        },
    ],
    responses={
        200: {
            "description": "Отчёт с метриками по вариантам",
            "schema": ReportExperimentResponseSchema,
        },
        400: {"description": "Некорректное окно (start >= end или невалидный ISO)"},
        404: {"description": "Эксперимент не найден"},
    },
)
@validate.validate(ReportsExperiment)
async def reports_experiment(request: web.Request, parsed: ReportsExperiment) -> web.Response:
    record_report_requested()
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    report = await get_experiment_report(experiment, parsed.start, parsed.end)
    return web.json_response(report, status=200)


@docs(
    tags=["Reports"],
    summary="Каталог метрик",
    description=(
        "Список настраиваемых метрик каталога. Метрики задаются аналитиком в админке: "
        "уникальный идентификатор (key), название, назначение, правило вычисления по событиям "
        "(какие события и как агрегируются), условия атрибуции (например, требовать подтверждённый факт показа). "
        "В отчёте по эксперименту используются метрики, выбранные для этого эксперимента (основная и дополнительные)."
    ),
    responses={
        200: {"description": "Список метрик каталога", "schema": MetricsListResponseSchema},
        401: {"description": "Требуется авторизация"},
    },
)
async def metrics_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] not in ["viewer", "experimenter", "approver"]:
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    items = await list_metrics()
    return web.json_response({"metrics": items})


@docs(
    tags=["Reports"],
    summary="Получить метрику по ключу",
    description="Получить одну метрику из каталога по уникальному ключу (идентификатору).",
    parameters=[
        {
            "name": "key",
            "in": "path",
            "required": True,
            "description": "Уникальный ключ метрики",
            "type": "string",
        },
    ],
    responses={
        200: {"description": "Метрика из каталога", "schema": MetricCatalogItemSchema},
        401: {"description": "Требуется авторизация"},
        404: {"description": "Метрика не найдена"},
    },
)
async def metrics_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] not in ["viewer", "experimenter", "approver"]:
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    key = _metric_key_from_request(request)
    if not key:
        return validate.format_404_error(request, "Metric key is required")
    item = await get_metric_by_key(key)
    if not item:
        return validate.format_404_error(request, "Metric not found")
    return web.json_response(item)


@docs(
    tags=["Reports"],
    summary="Создать метрику в каталоге",
    description=(
        "Создать настраиваемую метрику (Experimenter). Задаются: ключ, название, назначение, "
        "правило вычисления по событиям (aggregation_rule: count_events, ratio, avg, percentile), "
        "условия атрибуции (attribution_rule), единица измерения (unit)."
    ),
    responses={
        201: {"description": "Метрика создана", "schema": MetricCatalogItemSchema},
        400: {"description": "Некорректный запрос (неверный ключ, правило и т.д.)"},
        401: {"description": "Требуется авторизация"},
        403: {"description": "Только для админа"},
        409: {"description": "Метрика с таким ключом уже существует"},
    },
)
@request_schema(MetricCatalogCreateSchema(), location="json", put_into="data")
@validate.validate(MetricsCreate)
async def metrics_create(request: web.Request, parsed: MetricsCreate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload["role"] != "experimenter":
        return validate.format_403_error(request, "Only experimenter can create metrics")

    try:
        created, err = await create_metric(
            key=parsed.key,
            name=parsed.name,
            aggregation_rule=parsed.aggregation_rule,
            description=parsed.description,
            attribution_rule=parsed.attribution_rule,
            event_expectations=parsed.event_expectations,
            unit=parsed.unit,
        )
    except Exception as e:
        return web.json_response(
            validate.format_error_response(
                code="INTERNAL_ERROR",
                message="Failed to create metric",
                path=str(request.path_qs),
                status=500,
                details={"error": str(e)},
            ),
            status=500,
        )
    if err == "duplicate_key":
        return validate.format_409_error(
            request, parsed.key, "Metric with this key already exists", field="key"
        )
    if err in ("invalid_key", "invalid_name", "invalid_aggregation_rule"):
        return web.json_response(
            validate.format_error_response(
                code="BAD_REQUEST",
                message="Invalid metric data",
                path=str(request.path_qs),
                status=400,
                details={"error": err},
            ),
            status=400,
        )
    if err == "db_error" or not created:
        return web.json_response(
            validate.format_error_response(
                code="INTERNAL_ERROR",
                message="Failed to create metric",
                path=str(request.path_qs),
                status=500,
            ),
            status=500,
        )
    return web.json_response(created, status=201)


@docs(
    tags=["Reports"],
    summary="Обновить метрику в каталоге",
    description="Обновить метрику по ключу (Админ). Передаются только изменяемые поля.",
    parameters=[
        {
            "name": "key",
            "in": "path",
            "required": True,
            "description": "Уникальный ключ метрики",
            "type": "string",
        },
    ],
    responses={
        200: {"description": "Метрика обновлена", "schema": MetricCatalogItemSchema},
        400: {"description": "Некорректный запрос"},
        401: {"description": "Требуется авторизация"},
        403: {"description": "Только для админа"},
        404: {"description": "Метрика не найдена"},
    },
)
@request_schema(MetricCatalogUpdateSchema(), location="json", put_into="data")
@validate.validate(MetricsUpdate)
async def metrics_update(request: web.Request, parsed: MetricsUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "admin":
        return validate.format_403_error(request, "Only admin can update metrics")

    key = _metric_key_from_request(request)
    if not key:
        return validate.format_404_error(request, "Metric key is required")

    updated, err = await update_metric(
        key=key,
        name=parsed.name,
        description=parsed.description,
        aggregation_rule=parsed.aggregation_rule,
        attribution_rule=parsed.attribution_rule,
        event_expectations=parsed.event_expectations,
        unit=parsed.unit,
    )
    if err == "not_found":
        return validate.format_404_error(request, "Metric not found")
    if err == "db_error" or not updated:
        return web.json_response(
            validate.format_error_response(
                code="INTERNAL_ERROR",
                message="Failed to update metric",
                path=str(request.path_qs),
                status=500,
            ),
            status=500,
        )
    return web.json_response(updated, status=200)
