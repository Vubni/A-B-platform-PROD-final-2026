from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from autopilot_ramp import (
    create_or_update_ramp_plan,
    delete_ramp_plan,
    get_ramp_decision_log,
    get_ramp_plan_by_experiment_id,
    get_ramp_state,
    override_step,
    set_ramp_mode,
    start_autopilot,
)
from autopilot_ramp.types import RAMP_MODES
from core import check_authorization, validate_uuid
from docs.schems import (
    RAMP_DECISION_LOG_RESPONSE_EXAMPLE,
    RAMP_PLAN_RESPONSE_EXAMPLE,
    RAMP_STATE_RESPONSE_EXAMPLE,
    RESPONSES_HTTP_ERROR,
    RampDecisionLogResponseSchema,
    RampModePatchSchema,
    RampOverridePostSchema,
    RampPlanPutSchema,
    RampPlanSchema,
    RampStateSchema,
)
from functions.experiments import get_experiment_by_id


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    return validate_uuid(raw)


async def _require_experimenter_access(
    request: web.Request, experiment_id: str
) -> web.Response | None:
    auth = await check_authorization(request)
    if not auth:
        return validate.format_401_error(request)
    role = auth.get("role")
    if role != "experimenter":
        return validate.format_403_error(request, "Only experimenter can manage autopilot")
    user_id = str(auth["id"])
    experiment = await get_experiment_by_id(experiment_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    created_by = str(experiment.get("created_by") or "")
    if created_by and created_by != user_id:
        return validate.format_403_error(request, "Not enough permissions for this experiment")
    return None


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Получить план раскатки",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        200: {
            "schema": RampPlanSchema,
            "examples": {"application/json": RAMP_PLAN_RESPONSE_EXAMPLE},
        },
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def ramp_plan_get(request: web.Request) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    plan = await get_ramp_plan_by_experiment_id(exp_id)
    if not plan:
        return validate.format_404_error(request, "Ramp plan not found for this experiment")
    return web.json_response(plan)


class RampPlanPutBody(BaseModel):
    observation_window_seconds: int
    steps: list[dict]
    gate_data_sufficiency: dict | None = None
    gate_safety: dict | None = None
    gate_data_health: dict | None = None
    safety_actions: list[dict] | None = None

    @field_validator("observation_window_seconds")
    @classmethod
    def window_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("observation_window_seconds must be positive")
        if v > 86400 * 365:
            raise ValueError("observation_window_seconds must not exceed 31536000 (1 year)")
        return v

    @field_validator("steps")
    @classmethod
    def steps_non_empty_and_valid(cls, v: list) -> list:
        if not v:
            raise ValueError("steps must be non-empty")
        for i, s in enumerate(v):
            if not isinstance(s, dict):
                raise ValueError(f"steps[{i}] must be an object")
            tf = s.get("traffic_fraction")
            if tf is None:
                raise ValueError(f"steps[{i}].traffic_fraction is required")
            try:
                tf = float(tf)
            except (TypeError, ValueError) as err:
                raise ValueError(f"steps[{i}].traffic_fraction must be a number") from err
            if not (0 < tf <= 1):
                raise ValueError(f"steps[{i}].traffic_fraction must be in (0, 1]")
        return v


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Создать или обновить план раскатки",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        200: {
            "schema": RampPlanSchema,
            "examples": {"application/json": RAMP_PLAN_RESPONSE_EXAMPLE},
        },
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
        422: RESPONSES_HTTP_ERROR[422],
    },
)
@request_schema(RampPlanPutSchema(), location="json", put_into="data")
@validate.validate(RampPlanPutBody, require_auth=False)
async def ramp_plan_put(request: web.Request, parsed: RampPlanPutBody) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    plan, err = await create_or_update_ramp_plan(
        experiment_id=exp_id,
        observation_window_seconds=parsed.observation_window_seconds,
        steps=parsed.steps,
        gate_data_sufficiency=parsed.gate_data_sufficiency,
        gate_safety=parsed.gate_safety,
        gate_data_health=parsed.gate_data_health,
        safety_actions=parsed.safety_actions or [],
    )
    if err == "experiment_not_found":
        return validate.format_404_error(request, "Experiment not found")
    if err:
        return web.json_response({"error": err}, status=400)
    return web.json_response(plan)


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Удалить план раскатки",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        204: {},
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def ramp_plan_delete(request: web.Request) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    deleted = await delete_ramp_plan(exp_id)
    if not deleted:
        return validate.format_404_error(request, "Ramp plan not found")
    return web.Response(status=204)


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Получить состояние автопилота",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        200: {
            "schema": RampStateSchema,
            "examples": {"application/json": RAMP_STATE_RESPONSE_EXAMPLE},
        },
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def ramp_state_get(request: web.Request) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    state = await get_ramp_state(exp_id)
    if not state:
        return validate.format_404_error(request, "Autopilot not started for this experiment")
    return web.json_response(state)


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Запустить автопилот",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        200: {
            "schema": RampStateSchema,
            "examples": {"application/json": RAMP_STATE_RESPONSE_EXAMPLE},
        },
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def ramp_start_post(request: web.Request) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    state, err = await start_autopilot(exp_id)
    if err == "ramp_plan_not_found":
        return validate.format_404_error(request, "Ramp plan not found")
    if err == "experiment_not_running":
        return web.json_response(
            {"error": "Experiment must be running to start autopilot"}, status=400
        )
    if err == "already_started":
        return web.json_response({"error": "Autopilot already started"}, status=400)
    if err:
        return web.json_response({"error": err}, status=400)
    return web.json_response(state)


class RampModeBody(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def mode_valid(cls, v: str) -> str:
        if v not in RAMP_MODES:
            raise ValueError(f"mode must be one of {RAMP_MODES}")
        return v


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Установить режим автопилота",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        200: {
            "schema": RampStateSchema,
            "examples": {"application/json": RAMP_STATE_RESPONSE_EXAMPLE},
        },
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
@request_schema(RampModePatchSchema(), location="json", put_into="data")
@validate.validate(RampModeBody, require_auth=False)
async def ramp_mode_patch(request: web.Request, parsed: RampModeBody) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    auth = await check_authorization(request)
    user_id = str(auth.get("id") or "") if auth else None
    state, err = await set_ramp_mode(exp_id, parsed.mode, user_id)
    if err == "ramp_not_started":
        return validate.format_404_error(request, "Autopilot not started")
    if err:
        return web.json_response({"error": err}, status=400)
    return web.json_response(state)


class RampOverrideBody(BaseModel):
    to_step_index: int

    @field_validator("to_step_index")
    @classmethod
    def step_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("to_step_index must be >= 0")
        return v


@docs(
    tags=["Autopilot Ramp-up"],
    summary="Ручной переход на ступень",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        }
    ],
    responses={
        200: {
            "schema": RampStateSchema,
            "examples": {"application/json": RAMP_STATE_RESPONSE_EXAMPLE},
        },
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
@request_schema(RampOverridePostSchema(), location="json", put_into="data")
@validate.validate(RampOverrideBody, require_auth=False)
async def ramp_override_post(request: web.Request, parsed: RampOverrideBody) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    auth = await check_authorization(request)
    user_id = str(auth.get("id") or "") if auth else None
    if not user_id:
        return validate.format_401_error(request)
    state, err = await override_step(exp_id, parsed.to_step_index, user_id)
    if err == "ramp_not_started":
        return validate.format_404_error(request, "Autopilot not started")
    if err == "override_only_in_manual_mode":
        return web.json_response(
            {"error": "Override is only allowed when mode is manual"}, status=400
        )
    if err == "invalid_step_index":
        return web.json_response({"error": "Invalid step index"}, status=400)
    if err:
        return web.json_response({"error": err}, status=400)
    return web.json_response(state)


@docs(
    tags=["Autopilot Ramp-up"],
    summary="История решений автопилота",
    parameters=[
        {
            "name": "id",
            "in": "path",
            "required": True,
            "description": "UUID эксперимента",
            "schema": {"type": "string", "format": "uuid"},
        },
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "description": "Лимит записей (1..500), по умолчанию 100",
            "schema": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
        },
    ],
    responses={
        200: {
            "description": "Список записей лога",
            "schema": RampDecisionLogResponseSchema,
            "examples": {"application/json": RAMP_DECISION_LOG_RESPONSE_EXAMPLE},
        },
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def ramp_decision_log_get(request: web.Request) -> web.Response:
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    err_resp = await _require_experimenter_access(request, exp_id)
    if err_resp is not None:
        return err_resp

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    try:
        limit = int(request.query.get("limit", 100))
        limit = min(max(limit, 1), 500)
    except (TypeError, ValueError):
        limit = 100

    log = await get_ramp_decision_log(exp_id, limit=limit)
    return web.json_response({"decisions": log})
