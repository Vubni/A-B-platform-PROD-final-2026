from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, Field, field_validator

from api import validate
from core import check_authorization, validate_uuid
from docs.schems import (
    LearningAuditListResponseSchema,
    LearningItemSchema,
    LearningListQuerySchema,
    LearningListResponseSchema,
    LearningSimilarResponseSchema,
    LearningUpsertSchema,
    RESPONSES_HTTP_ERROR,
)
from functions.experiments import get_experiment_by_id
from functions.learnings import (
    LEARNING_ACTIONS,
    LEARNING_OUTCOMES,
    find_similar_learnings,
    get_learning_by_experiment_id,
    get_learning_by_id,
    list_learning_audit,
    list_learnings,
    upsert_learning,
)


def _learning_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    if not raw:
        return None
    return validate_uuid(raw)


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    if not raw:
        return None
    return validate_uuid(raw)


def _parse_csv_list(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        out = [str(x).strip() for x in value if str(x).strip()]
        return out
    out = [x.strip() for x in str(value).split(",") if x.strip()]
    return out


class LearningAuditQuery(BaseModel):
    limit: int = 50
    offset: int = 0

    @field_validator("limit")
    @classmethod
    def limit_bounds(cls, v: int) -> int:
        if v < 1 or v > 200:
            raise ValueError("limit must be in [1, 200]")
        return v

    @field_validator("offset")
    @classmethod
    def offset_bounds(cls, v: int) -> int:
        if v < 0:
            raise ValueError("offset must be >= 0")
        return v

class LearningGuardrailItem(BaseModel):
    metric_key: str
    threshold_value: float | None = None
    trigger_count: int = 0
    details: dict = Field(default_factory=dict)

    @field_validator("metric_key")
    @classmethod
    def metric_key_nonempty(cls, v: str) -> str:
        if not v or not v.strip() or len(v.strip()) > 255:
            raise ValueError("metric_key is required, max 255 chars")
        return v.strip()

    @field_validator("trigger_count")
    @classmethod
    def trigger_count_nonnegative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("trigger_count must be >= 0")
        return v


class LearningUpsert(BaseModel):
    owner_user_id: str | None = None
    owner_team: str | None = None
    hypothesis: str
    primary_metric_key: str
    result_outcome: str
    result_action: str
    effect_summary: str | None = None
    targeting_summary: str | None = None
    platforms: list[str] | None = None
    countries: list[str] | None = None
    app_versions: list[str] | None = None
    product_tags: list[str] | None = None
    change_type: str | None = None
    variant_structure: dict = Field(default_factory=dict)
    report_url: str | None = None
    ticket_url: str | None = None
    notes: str
    is_completed: bool = False
    guardrails: list[LearningGuardrailItem] = Field(default_factory=list)

    @field_validator("owner_user_id")
    @classmethod
    def owner_user_id_valid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        u = validate_uuid(v)
        if not u:
            raise ValueError("owner_user_id must be valid UUID")
        return u

    @field_validator("owner_team")
    @classmethod
    def owner_team_len(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) > 255:
            raise ValueError("owner_team max 255 chars")
        return v.strip() if v is not None else v

    @field_validator("hypothesis")
    @classmethod
    def hypothesis_required(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("hypothesis is required")
        if len(s) > 5000:
            raise ValueError("hypothesis max 5000 chars")
        return s

    @field_validator("primary_metric_key")
    @classmethod
    def primary_metric_key_valid(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("primary_metric_key is required")
        if len(s) > 255:
            raise ValueError("primary_metric_key max 255 chars")
        return s

    @field_validator("result_outcome")
    @classmethod
    def outcome_one_of(cls, v: str) -> str:
        if v not in LEARNING_OUTCOMES:
            raise ValueError(f"result_outcome must be one of {LEARNING_OUTCOMES}")
        return v

    @field_validator("result_action")
    @classmethod
    def action_one_of(cls, v: str) -> str:
        if v not in LEARNING_ACTIONS:
            raise ValueError(f"result_action must be one of {LEARNING_ACTIONS}")
        return v

    @field_validator("effect_summary")
    @classmethod
    def effect_summary_len(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) > 255:
            raise ValueError("effect_summary max 255 chars")
        return v.strip() if v is not None else v

    @field_validator("notes")
    @classmethod
    def notes_required(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("notes is required")
        if len(s) > 5000:
            raise ValueError("notes max 5000 chars")
        return s

    @field_validator("platforms", "countries", "app_versions", "product_tags")
    @classmethod
    def arrays_clean(cls, v: list[str] | None) -> list[str]:
        if not v:
            return []
        out = []
        for item in v:
            s = str(item).strip()
            if not s:
                continue
            if len(s) > 255:
                raise ValueError("Array item max 255 chars")
            out.append(s)
        return out


class LearningListQuery(BaseModel):
    q: str | None = None
    flag_key: str | None = None
    owner_user_id: str | None = None
    owner_team: str | None = None
    result_outcome: str | None = None
    primary_metric_key: str | None = None
    countries: list[str] | None = None
    platforms: list[str] | None = None
    tags: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = 20
    offset: int = 0

    @field_validator("q")
    @classmethod
    def q_len(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) > 500:
            raise ValueError("q max 500 chars")
        return v.strip() if v else v

    @field_validator("flag_key")
    @classmethod
    def flag_key_len(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) > 255:
            raise ValueError("flag_key max 255 chars")
        return v.strip() if v else v

    @field_validator("owner_user_id")
    @classmethod
    def owner_uuid(cls, v: str | None) -> str | None:
        if not v:
            return None
        u = validate_uuid(v)
        if not u:
            raise ValueError("owner_user_id must be valid UUID")
        return u

    @field_validator("owner_team", "primary_metric_key", mode="before")
    @classmethod
    def simple_trim(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None

    @field_validator("result_outcome")
    @classmethod
    def result_outcome_one_of(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in LEARNING_OUTCOMES:
            raise ValueError(f"result_outcome must be one of {LEARNING_OUTCOMES}")
        return v

    @field_validator("countries", "platforms", "tags", mode="before")
    @classmethod
    def parse_list(cls, v):
        return _parse_csv_list(v)

    @field_validator("limit")
    @classmethod
    def limit_bounds(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("limit must be in [1, 100]")
        return v

    @field_validator("offset")
    @classmethod
    def offset_bounds(cls, v: int) -> int:
        if v < 0:
            raise ValueError("offset must be >= 0")
        return v


class SimilarQuery(BaseModel):
    limit: int = 5

    @field_validator("limit")
    @classmethod
    def limit_bounds(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("limit must be in [1, 20]")
        return v


@docs(
    tags=["Learnings"],
    summary="Поиск learnings",
    responses={200: {"description": "Список learnings", "schema": LearningListResponseSchema}, 
    401: RESPONSES_HTTP_ERROR[401], 
    422: RESPONSES_HTTP_ERROR[422],
    404: RESPONSES_HTTP_ERROR[404],
    500: RESPONSES_HTTP_ERROR[500],
    },
)
@request_schema(LearningListQuerySchema(), location="query", put_into="data")
@validate.validate(LearningListQuery)
async def learnings_list(request: web.Request, parsed: LearningListQuery) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    rows = await list_learnings(
        q=parsed.q,
        flag_key=parsed.flag_key,
        owner_user_id=parsed.owner_user_id,
        owner_team=parsed.owner_team,
        result_outcome=parsed.result_outcome,
        primary_metric_key=parsed.primary_metric_key,
        countries=parsed.countries,
        platforms=parsed.platforms,
        tags=parsed.tags,
        date_from=parsed.date_from,
        date_to=parsed.date_to,
        limit=parsed.limit,
        offset=parsed.offset)
    return web.json_response({"learnings": rows})


@docs(
    tags=["Learnings"],
    summary="Получить learning по id",
    responses={200: {"description": "Learning", "schema": LearningItemSchema}, 
    401: RESPONSES_HTTP_ERROR[401], 
    404: RESPONSES_HTTP_ERROR[404],
    422: RESPONSES_HTTP_ERROR[422],
    500: RESPONSES_HTTP_ERROR[500],
    },
)
async def learnings_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    learning_id = _learning_id_from_request(request)
    if not learning_id:
        return validate.format_404_error(request, "Invalid learning id")

    row = await get_learning_by_id(learning_id)
    if not row:
        return validate.format_404_error(request, "Learning not found")
    return web.json_response(row)


@docs(
    tags=["Learnings"],
    summary="Получить learning по эксперименту",
    responses={200: {"description": "Learning", "schema": LearningItemSchema}, 
    401: RESPONSES_HTTP_ERROR[401], 
    404: RESPONSES_HTTP_ERROR[404],
    422: RESPONSES_HTTP_ERROR[422],
    500: RESPONSES_HTTP_ERROR[500],
    },
)
async def learning_by_experiment_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    experiment_id = _experiment_id_from_request(request)
    if not experiment_id:
        return validate.format_404_error(request, "Invalid experiment id")

    row = await get_learning_by_experiment_id(experiment_id)
    if not row:
        return validate.format_404_error(request, "Learning not found")
    return web.json_response(row)


@docs(
    tags=["Learnings"],
    summary="Создать или обновить learning для эксперимента",
    responses={200: {"description": "Learning", "schema": LearningItemSchema}, 
    401: RESPONSES_HTTP_ERROR[401], 
    403: RESPONSES_HTTP_ERROR[403], 
    404: RESPONSES_HTTP_ERROR[404], 
    422: RESPONSES_HTTP_ERROR[422],
    500: RESPONSES_HTTP_ERROR[500],
    },
)
@request_schema(LearningUpsertSchema(), location="json", put_into="data")
@validate.validate(LearningUpsert)
async def learning_upsert_for_experiment(request: web.Request, parsed: LearningUpsert) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    if auth_payload.get("role") not in ("admin", "experimenter"):
        return validate.format_403_error(request, "Not enough permissions")

    experiment_id = _experiment_id_from_request(request)
    if not experiment_id:
        return validate.format_404_error(request, "Invalid experiment id")
    experiment = await get_experiment_by_id(experiment_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    is_owner = str(experiment.get("created_by")) == str(auth_payload.get("id"))
    if auth_payload.get("role") != "admin" and not is_owner:
        return validate.format_403_error(request, "Only owner or admin can write learnings")

    row = await upsert_learning(
        experiment_id=experiment_id,
        flag_key=experiment.get("flag_key"),
        owner_user_id=parsed.owner_user_id,
        owner_team=parsed.owner_team,
        hypothesis=parsed.hypothesis,
        primary_metric_key=parsed.primary_metric_key,
        result_outcome=parsed.result_outcome,
        result_action=parsed.result_action,
        effect_summary=parsed.effect_summary,
        targeting_summary=parsed.targeting_summary,
        platforms=parsed.platforms,
        countries=parsed.countries,
        app_versions=parsed.app_versions,
        product_tags=parsed.product_tags,
        change_type=parsed.change_type,
        variant_structure=parsed.variant_structure,
        report_url=parsed.report_url,
        ticket_url=parsed.ticket_url,
        notes=parsed.notes,
        is_completed=parsed.is_completed,
        guardrails=[
            {
                "metric_key": g.metric_key,
                "threshold_value": g.threshold_value,
                "trigger_count": g.trigger_count,
                "details": g.details,
            }
            for g in parsed.guardrails
        ],
        actor_user_id=str(auth_payload.get("id")) if auth_payload.get("id") else None)
    return web.json_response(row)


@docs(
    tags=["Learnings"],
    summary="История изменений learning",
    responses={200: {"description": "Аудит", "schema": LearningAuditListResponseSchema}, 
    401: RESPONSES_HTTP_ERROR[401], 
    404: RESPONSES_HTTP_ERROR[404],
    422: RESPONSES_HTTP_ERROR[422],
    500: RESPONSES_HTTP_ERROR[500],
    },
)
@validate.validate(LearningAuditQuery)
async def learnings_audit(request: web.Request, parsed: LearningAuditQuery) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    learning_id = _learning_id_from_request(request)
    if not learning_id:
        return validate.format_404_error(request, "Invalid learning id")

    row = await get_learning_by_id(learning_id)
    if not row:
        return validate.format_404_error(request, "Learning not found")

    records = await list_learning_audit(learning_id, parsed.limit, parsed.offset)
    return web.json_response({"learning_id": learning_id, "audit": records})


@docs(
    tags=["Learnings"],
    summary="Похожие эксперименты для learning",
    responses={200: {"description": "Похожие learnings", "schema": LearningSimilarResponseSchema}, 
    401: RESPONSES_HTTP_ERROR[401], 
    404: RESPONSES_HTTP_ERROR[404], 
    422: RESPONSES_HTTP_ERROR[422],
    500: RESPONSES_HTTP_ERROR[500],
    },
)
@validate.validate(SimilarQuery)
async def learnings_similar(request: web.Request, parsed: SimilarQuery) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    learning_id = _learning_id_from_request(request)
    if not learning_id:
        return validate.format_404_error(request, "Invalid learning id")

    row = await get_learning_by_id(learning_id)
    if not row:
        return validate.format_404_error(request, "Learning not found")

    similar = await find_similar_learnings(learning_id, parsed.limit)
    return web.json_response({"learning_id": learning_id, "similar": similar})
