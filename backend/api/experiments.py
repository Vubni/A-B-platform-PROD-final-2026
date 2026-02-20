from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator, model_validator

from api import validate
from core import check_authorization, validate_uuid
from docs.schems import (
    CompleteExperimentSchema,
    ExperimentCreateSchema,
    ExperimentItemSchema,
    ExperimentListResponseSchema,
    ExperimentUpdateSchema,
    ExperimentVariantSchema,
    GuardrailHistoryResponseSchema,
    StatusUpdateSchema,
    VariantCreateSchema,
    VariantUpdateSchema,
)
from dsl import validate_targeting_rule
from functions.experiments import (
    add_experiment_variant,
    check_access_to_experiment,
    complete_experiment,
    create_experiment,
    delete_experiment_variant,
    get_experiment_by_id,
    get_experiments_list,
    get_guardrail_history,
    update_experiment,
    update_experiment_status,
    update_experiment_variant,
)

VALID_STATUSES = (
    "draft",
    "on_review",
    "approved",
    "running",
    "paused",
    "completed",
    "archived",
    "rejected",
)
METRIC_TYPES = ("primary", "auxiliary", "guardrail")


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    if not raw:
        return None
    return validate_uuid(raw) if validate_uuid(raw) else None


def _variant_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("variant_id", "").strip()
    if not raw:
        return None
    return validate_uuid(raw) if validate_uuid(raw) else None


class ExperimentMetricItem(BaseModel):
    metric_key: str
    metric_type: str

    @field_validator("metric_key")
    @classmethod
    def key_nonempty(cls, v: str) -> str:
        if not v or not v.strip() or len(v) > 255:
            raise ValueError("metric_key: non-empty, max 255 chars")
        return v.strip()

    @field_validator("metric_type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in METRIC_TYPES:
            raise ValueError(f"metric_type must be one of {METRIC_TYPES}")
        return v


class ExperimentCreate(BaseModel):
    flag_id: str
    name: str
    audience_fraction: float
    targeting_rule: str | None = None
    metrics: list[ExperimentMetricItem] | None = None

    @field_validator("flag_id")
    @classmethod
    def flag_id_uuid(cls, v: str) -> str:
        u = validate_uuid(v)
        if not u:
            raise ValueError("Invalid UUID for flag_id")
        return u

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name is required")
        if len(v) > 255:
            raise ValueError("Name must be at most 255 characters")
        return v.strip()

    @field_validator("audience_fraction")
    @classmethod
    def audience_fraction_range(cls, v: float) -> float:
        if v is None or v <= 0 or v > 1:
            raise ValueError("Audience fraction must be in (0, 1]")
        return v

    @field_validator("targeting_rule")
    @classmethod
    def targeting_rule_opt(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 2048:
            raise ValueError("Targeting rule too long")
        if v is not None and not validate_targeting_rule(v):
            raise ValueError("Invalid targeting rule")
        return v

    @field_validator("metrics")
    @classmethod
    def metrics_one_primary(cls, v: list | None) -> list | None:
        if not v:
            return v
        primary_count = sum(1 for m in v if getattr(m, "metric_type", None) == "primary")
        if primary_count != 1:
            raise ValueError("Должна быть ровно одна метрика с metric_type 'primary'")
        return v


class ExperimentUpdate(BaseModel):
    name: str | None = None
    audience_fraction: float | None = None
    targeting_rule: str | None = None
    metrics: list[ExperimentMetricItem] | None = None

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str | None) -> str | None:
        if v is not None and (not v.strip() or len(v) > 255):
            raise ValueError("Name must be non-empty and at most 255 characters")
        return v.strip() if v else v

    @field_validator("audience_fraction")
    @classmethod
    def audience_fraction_range(cls, v: float | None) -> float | None:
        if v is not None and (v <= 0 or v > 1):
            raise ValueError("Audience fraction must be in (0, 1]")
        return v

    @field_validator("targeting_rule")
    @classmethod
    def targeting_rule_opt(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 2048:
            raise ValueError("Targeting rule too long")
        if v is not None and not validate_targeting_rule(v):
            raise ValueError("Invalid targeting rule")
        return v

    @field_validator("metrics")
    @classmethod
    def metrics_one_primary(cls, v: list | None) -> list | None:
        if not v:
            return v
        primary_count = sum(1 for m in v if getattr(m, "metric_type", None) == "primary")
        if primary_count != 1:
            raise ValueError("Должна быть ровно одна метрика с metric_type 'primary'")
        return v


class ReviewAction(BaseModel):
    comment: str | None = None


class StatusUpdate(BaseModel):
    status: str
    comment: str | None = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Status must be one of {VALID_STATUSES}")
        return v


class CompleteExperiment(BaseModel):
    completion_outcome: str
    comment: str
    completion_winner_variant_id: str | None = None

    @field_validator("completion_outcome")
    @classmethod
    def outcome_valid(cls, v: str) -> str:
        if v not in ("rollout_winner", "rollback", "no_effect"):
            raise ValueError(
                "completion_outcome must be one of: rollout_winner, rollback, no_effect"
            )
        return v

    @field_validator("comment")
    @classmethod
    def comment_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("comment is required")
        return v.strip()

    @model_validator(mode="after")
    def check_rollout_winner(self) -> "CompleteExperiment":
        if self.completion_outcome == "rollout_winner" and not self.completion_winner_variant_id:
            raise ValueError(
                "completion_winner_variant_id required when completion_outcome=rollout_winner"
            )
        return self


class VariantCreate(BaseModel):
    variant_name: str
    variant_value: str
    weight: float
    is_control: bool = False

    @field_validator("variant_name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v or not v.strip() or len(v) > 255:
            raise ValueError("variant_name: non-empty, max 255 chars")
        return v.strip()

    @field_validator("variant_value")
    @classmethod
    def value_len(cls, v: str) -> str:
        if len(v) > 2048:
            raise ValueError("variant_value max 2048 characters")
        return v

    @field_validator("weight")
    @classmethod
    def weight_nonneg(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weight must be >= 0")
        return v


class VariantUpdate(BaseModel):
    variant_value: str | None = None
    weight: float | None = None
    is_control: bool | None = None

    @field_validator("variant_value")
    @classmethod
    def value_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 2048:
            raise ValueError("variant_value max 2048 characters")
        return v

    @field_validator("weight")
    @classmethod
    def weight_nonneg(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("weight must be >= 0")
        return v


@docs(
    tags=["Experiments"],
    summary="Создать эксперимент",
    responses={
        201: {"description": "Эксперимент создан", "schema": ExperimentItemSchema},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Флаг не найден"},
    },
)
@request_schema(ExperimentCreateSchema(), location="json", put_into="data")
@validate.validate(ExperimentCreate)
async def experiments_create(request: web.Request, parsed: ExperimentCreate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "experimenter":
        return validate.format_403_error(request, "Not enough permissions to create experiments")

    created_by = auth_payload.get("id")
    metrics_payload = [
        {"metric_key": m.metric_key, "metric_type": m.metric_type} for m in (parsed.metrics or [])
    ]
    experiment, err_code, err_details = await create_experiment(
        flag_id=parsed.flag_id,
        name=parsed.name,
        audience_fraction=parsed.audience_fraction,
        created_by=created_by,
        targeting_rule=parsed.targeting_rule,
        metrics=metrics_payload if metrics_payload else None,
    )
    if err_code == "flag_not_found":
        return validate.format_404_error(request, "Flag not found", details={"field": "flag_id"})
    if err_code == "metrics_validation":
        return web.json_response(
            {"error": err_details[0] if err_details else "Invalid metrics"},
            status=400,
        )
    if err_code == "metrics_not_in_catalog":
        return web.json_response(
            {"error": "Метрики не найдены в каталоге", "unknown_keys": err_details or []},
            status=400,
        )
    return web.json_response(experiment, status=201)


@docs(
    tags=["Experiments"],
    summary="Список экспериментов",
    responses={
        200: {"description": "Список экспериментов", "schema": ExperimentListResponseSchema}
    },
)
async def experiments_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    flag_id = request.query.get("flag_id") or None
    status = request.query.get("status") or None
    if flag_id and not validate_uuid(flag_id):
        flag_id = None
    if status and status not in VALID_STATUSES:
        status = None

    experiments = await get_experiments_list(flag_id=flag_id, status=status)
    return web.json_response({"experiments": experiments})


@docs(
    tags=["Experiments"],
    summary="Получить эксперимент",
    responses={
        200: {"description": "Данные эксперимента", "schema": ExperimentItemSchema},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    return web.json_response(experiment)


@docs(
    tags=["Experiments"],
    summary="Обновить эксперимент",
    responses={
        200: {"description": "Эксперимент обновлён", "schema": ExperimentItemSchema},
        400: {"description": "Некорректный запрос или не в черновике"},
        404: {"description": "Эксперимент не найден"},
    },
)
@request_schema(ExperimentUpdateSchema(), location="json", put_into="data")
@validate.validate(ExperimentUpdate)
async def experiments_update(request: web.Request, parsed: ExperimentUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "experimenter":
        return validate.format_403_error(request, "Not enough permissions to update experiments")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    created_by = experiment.get("created_by")
    if str(created_by) != str(auth_payload.get("id")):
        return validate.format_403_error(request, "Only owner or admin can update this experiment")

    status = experiment.get("status")

    has_update = (
        parsed.name
        or parsed.audience_fraction
        or parsed.targeting_rule is not None
        or parsed.metrics is not None
    )
    if not has_update:
        return web.json_response(
            {"error": "No fields to update"},
            status=400,
        )

    if status == "draft":
        metrics_payload = None
        if parsed.metrics is not None:
            metrics_payload = [
                {"metric_key": m.metric_key, "metric_type": m.metric_type} for m in parsed.metrics
            ]
        updated, err_code, err_details = await update_experiment(
            experiment_id=exp_id,
            name=parsed.name,
            audience_fraction=parsed.audience_fraction,
            targeting_rule=parsed.targeting_rule,
            metrics=metrics_payload,
        )
        if err_code == "metrics_validation":
            return web.json_response(
                {"error": err_details[0] if err_details else "Invalid metrics"},
                status=400,
            )
        if err_code == "metrics_not_in_catalog":
            return web.json_response(
                {"error": "Метрики не найдены в каталоге", "unknown_keys": err_details or []},
                status=400,
            )
        return web.json_response(updated)

    if status in ("running", "paused", "completed", "archived"):
        if (
            parsed.audience_fraction
            or parsed.targeting_rule is not None
            or parsed.metrics is not None
        ):
            return web.json_response(
                {"error": "Experiment is frozen after start; only 'name' can be updated"},
                status=400,
            )

        updated, _err, _details = await update_experiment(experiment_id=exp_id, name=parsed.name)
        return web.json_response(updated)

    return web.json_response(
        {"error": "Experiment can be updated only in draft status", "status": status},
        status=400,
    )


@docs(
    tags=["Experiments"],
    summary="Обновить статус эксперимента",
    responses={
        200: {"description": "Статус обновлён", "schema": ExperimentItemSchema},
        400: {"description": "Недопустимый переход"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент не найден"},
        409: {"description": "Конфликт (другой эксперимент на флаг)"},
    },
)
@request_schema(StatusUpdateSchema(), location="json", put_into="data")
@validate.validate(StatusUpdate)
async def experiments_update_status(request: web.Request, parsed: StatusUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    current = experiment["status"]
    new_status = parsed.status
    user_id = str(auth_payload.get("id"))
    role = auth_payload.get("role")
    created_by = experiment["created_by"]
    is_owner = str(created_by) == user_id

    if current == "on_review" and new_status in ("draft", "rejected", "approved"):
        if role != "approver":
            return validate.format_403_error(request, "Only approvers can perform review actions")
        if not await check_access_to_experiment(exp_id, user_id):
            return validate.format_403_error(request, "Not enough permissions for this experiment")
        updated, status_err = await update_experiment_status(
            exp_id, new_status, comment=parsed.comment, reviewer_id=user_id
        )
    else:
        if role != "experimenter":
            return validate.format_403_error(
                request, "Only experimenters can change status to on_review/running/paused"
            )
        if not is_owner:
            return validate.format_403_error(
                request, "Only owner can change this experiment status"
            )
        updated, status_err = await update_experiment_status(
            exp_id, new_status, comment=parsed.comment, reviewer_id=user_id
        )

    if not updated:
        if new_status == "running":
            return validate.format_409_error(
                request, "Another experiment for this flag is already running"
            )
        if new_status == "paused":
            return validate.format_409_error(
                request, "Another experiment for this flag is already paused"
            )
        err = (
            status_err
            or "Invalid status transition or validation failed (e.g. add variants for on_review)"
        )
        return web.json_response({"error": err, "current_status": current}, status=400)
    return web.json_response(updated)


@docs(
    tags=["Experiments"],
    summary="Завершить эксперимент (финальное решение)",
    description=(
        "Experimenter явно завершает эксперимент и фиксирует решение: rollout_winner (раскатить победителя), "
        "rollback (откат к контролю) или no_effect (эффект не выявлен). Комментарий обязателен. "
        "Доступно только при статусе running или paused. Viewer затем может просмотреть результат по отчёту (GET report)."
    ),
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
        200: {"description": "Эксперимент завершён", "schema": ExperimentItemSchema},
        400: {"description": "Недопустимое состояние или неверный variant_id"},
        403: {"description": "Только experimenter и владелец"},
        404: {"description": "Эксперимент не найден"},
    },
)
@request_schema(CompleteExperimentSchema(), location="json", put_into="data")
@validate.validate(CompleteExperiment)
async def experiments_complete(request: web.Request, parsed: CompleteExperiment) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "experimenter":
        return validate.format_403_error(request, "Only experimenters can complete experiments")
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    if str(experiment["created_by"]) != str(auth_payload.get("id")):
        return validate.format_403_error(request, "Only owner can complete this experiment")
    if experiment["status"] not in ("running", "paused"):
        return web.json_response(
            {
                "error": "Experiment can be completed only when status is running or paused",
                "status": experiment["status"],
            },
            status=400,
        )
    if parsed.completion_outcome == "rollout_winner":
        variant_ids = [str(v.get("id")) for v in (experiment.get("variants") or []) if v.get("id")]
        if parsed.completion_winner_variant_id not in variant_ids:
            return web.json_response(
                {"error": "completion_winner_variant_id must be a variant of this experiment"},
                status=400,
            )
    updated = await complete_experiment(
        exp_id,
        outcome=parsed.completion_outcome,
        comment=parsed.comment,
        winner_variant_id=parsed.completion_winner_variant_id
        if parsed.completion_outcome == "rollout_winner"
        else None,
    )
    if not updated:
        return web.json_response({"error": "Failed to complete experiment"}, status=400)
    return web.json_response(updated)


@docs(
    tags=["Experiments"],
    summary="Добавить вариант к эксперименту",
    responses={
        201: {"description": "Вариант создан", "schema": ExperimentVariantSchema},
        400: {"description": "Эксперимент не в черновике"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент не найден"},
    },
)
@request_schema(VariantCreateSchema(), location="json", put_into="data")
@validate.validate(VariantCreate)
async def experiments_variant_create(request: web.Request, parsed: VariantCreate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "experimenter":
        return validate.format_403_error(request, "Not enough permissions")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    if experiment["status"] != "draft":
        return web.json_response(
            {"error": "Variants can be added only in draft", "status": experiment["status"]},
            status=400,
        )
    if str(experiment["created_by"]) != str(auth_payload.get("id")):
        return validate.format_403_error(request, "Only owner can add variants")

    variant = await add_experiment_variant(
        experiment_id=exp_id,
        variant_name=parsed.variant_name,
        variant_value=parsed.variant_value,
        weight=parsed.weight,
        is_control=parsed.is_control,
    )
    if not variant:
        return web.json_response(
            {"error": "Experiment not in draft or invariant violation (e.g. weights, control)"},
            status=400,
        )
    return web.json_response(variant, status=201)


@docs(
    tags=["Experiments"],
    summary="Обновить вариант эксперимента",
    responses={
        200: {"description": "Вариант обновлён", "schema": ExperimentVariantSchema},
        400: {"description": "Эксперимент не в черновике"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент или вариант не найден"},
    },
)
@request_schema(VariantUpdateSchema(), location="json", put_into="data")
@validate.validate(VariantUpdate)
async def experiments_variant_update(request: web.Request, parsed: VariantUpdate) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "experimenter":
        return validate.format_403_error(request, "Not enough permissions")

    exp_id = _experiment_id_from_request(request)
    variant_id = _variant_id_from_request(request)
    if not exp_id or not variant_id:
        return validate.format_404_error(request, "Invalid experiment id or variant id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    if experiment.get("status") != "draft":
        return web.json_response(
            {"error": "Variants can be updated only in draft", "status": experiment.get("status")},
            status=400,
        )
    if str(experiment.get("created_by")) != str(auth_payload.get("id")):
        return validate.format_403_error(request, "Only owner can update variants")

    variant = await update_experiment_variant(
        experiment_id=exp_id,
        variant_id=variant_id,
        variant_value=parsed.variant_value,
        weight=parsed.weight,
        is_control=parsed.is_control,
    )
    if not variant:
        return validate.format_404_error(request, "Variant not found or experiment not in draft")
    return web.json_response(variant)


@docs(
    tags=["Experiments"],
    summary="Удалить вариант эксперимента",
    responses={
        204: {"description": "Вариант удалён"},
        400: {"description": "Эксперимент не в черновике"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_variant_delete(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") != "experimenter":
        return validate.format_403_error(request, "Not enough permissions")

    exp_id = _experiment_id_from_request(request)
    variant_id = _variant_id_from_request(request)
    if not exp_id or not variant_id:
        return validate.format_404_error(request, "Invalid experiment id or variant id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")
    if experiment.get("status") != "draft":
        return web.json_response(
            {"error": "Variants can be deleted only in draft", "status": experiment.get("status")},
            status=400,
        )
    if str(experiment.get("created_by")) != str(auth_payload.get("id")):
        return validate.format_403_error(request, "Only owner can delete variants")

    ok = await delete_experiment_variant(experiment_id=exp_id, variant_id=variant_id)
    if not ok:
        return validate.format_404_error(request, "Variant not found or experiment not in draft")
    return web.Response(status=204)


@docs(
    tags=["Experiments"],
    summary="История срабатываний guardrail",
    responses={
        200: {"description": "История guardrail", "schema": GuardrailHistoryResponseSchema},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_guardrail_history(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    triggers = await get_guardrail_history(exp_id)
    return web.json_response(
        {
            "experiment_id": exp_id,
            "triggers": triggers or [],
        }
    )
