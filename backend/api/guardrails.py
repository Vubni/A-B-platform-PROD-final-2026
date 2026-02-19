from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from core import check_authorization
from docs.schems import (
    ExperimentGuardrailItemSchema,
    ExperimentGuardrailUpsertSchema,
    ExperimentGuardrailListResponseSchema,
)
from functions.guardrails import (
    list_metric_guardrails,
    get_metric_guardrail,
    upsert_metric_guardrail,
    delete_metric_guardrail,
)


class MetricGuardrailUpsert(BaseModel):
    metric_key: str
    threshold: float
    window_seconds: int
    action: str

    @field_validator("metric_key")
    @classmethod
    def metric_key_nonempty(cls, v: str) -> str:
        if not v or not v.strip() or len(v) > 255:
            raise ValueError("metric_key: non-empty, max 255 chars")
        return v.strip()

    @field_validator("window_seconds")
    @classmethod
    def window_positive(cls, v: int) -> int:
        if v is None or v <= 0:
            raise ValueError("window_seconds must be > 0")
        return v

    @field_validator("action")
    @classmethod
    def action_valid(cls, v: str) -> str:
        allowed = ("pause", "rollback_to_control")
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v


def _metric_key_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("metric_key", "").strip()
    return raw or None


@docs(
    tags=["Guardrails"],
    summary="Список guardrail-правил по метрикам",
    description="Получить список guardrail-правил, привязанных к метрикам (viewer/experimenter).",
    responses={
        200: {"description": "Список guardrails", "schema": ExperimentGuardrailListResponseSchema},
    },
)
async def guardrails_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    role = auth_payload.get("role")
    if role not in ("viewer", "experimenter", "approver", "admin"):
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    items = await list_metric_guardrails()
    return web.json_response({"guardrails": items})


@docs(
    tags=["Guardrails"],
    summary="Получить guardrail по метрике",
    description="Получить guardrail-правило по metric_key.",
    responses={
        200: {"description": "Guardrail по метрике", "schema": ExperimentGuardrailItemSchema},
        404: {"description": "Guardrail не найден"},
    },
)
async def guardrails_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    role = auth_payload.get("role")
    if role not in ("viewer", "experimenter", "approver", "admin"):
        return validate.format_403_error(request, "Not enough permissions to access this resource")

    metric_key = _metric_key_from_request(request)
    if not metric_key:
        return validate.format_404_error(request, "Metric key is required")

    item = await get_metric_guardrail(metric_key)
    if not item:
        return validate.format_404_error(request, "Guardrail not found")
    return web.json_response(item)


@docs(
    tags=["Guardrails"],
    summary="Создать или обновить guardrail по метрике",
    description="Создать или обновить guardrail-правило по metric_key (experimenter/admin). Метрика должна существовать в каталоге.",
    responses={
        200: {"description": "Guardrail сохранён", "schema": ExperimentGuardrailItemSchema},
        400: {"description": "Некорректный запрос"},
        403: {"description": "Нет прав"},
        404: {"description": "Метрика не найдена"},
    },
)
@request_schema(ExperimentGuardrailUpsertSchema(), location="json", put_into="data")
@validate.validate(MetricGuardrailUpsert)
async def guardrails_upsert(request: web.Request, parsed: MetricGuardrailUpsert) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") not in ("experimenter", "admin"):
        return validate.format_403_error(request, "Only experimenter or admin can manage guardrails")

    item = await upsert_metric_guardrail(
        metric_key=parsed.metric_key,
        threshold=parsed.threshold,
        window_seconds=parsed.window_seconds,
        action=parsed.action,
    )
    if not item:
        return validate.format_404_error(request, "Metric not found")
    return web.json_response(item, status=200)


@docs(
    tags=["Guardrails"],
    summary="Удалить guardrail по метрике",
    description="Удалить guardrail-правило по metric_key (experimenter/admin).",
    responses={
        204: {"description": "Guardrail удалён"},
        403: {"description": "Нет прав"},
        404: {"description": "Guardrail не найден"},
    },
)
async def guardrails_delete(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") not in ("experimenter", "admin"):
        return validate.format_403_error(request, "Only experimenter or admin can manage guardrails")

    metric_key = _metric_key_from_request(request)
    if not metric_key:
        return validate.format_404_error(request, "Metric key is required")

    ok = await delete_metric_guardrail(metric_key)
    if not ok:
        return validate.format_404_error(request, "Guardrail not found")
    return web.Response(status=204)

