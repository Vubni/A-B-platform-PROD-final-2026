from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from core import check_authorization, validate_uuid
from database.database import Database
from docs.schems import (
    RESPONSES_HTTP_ERROR,
    ConflictBindingItemSchema,
    ConflictBindingListResponseSchema,
    ConflictBindingUpsertSchema,
    ConflictDomainCreateSchema,
    ConflictDomainItemSchema,
    ConflictDomainListResponseSchema,
    ConflictDomainUpdateSchema,
    ConflictPreflightResponseSchema,
)
from functions.conflicts import (
    create_domain,
    delete_binding,
    delete_domain,
    get_conflict_log_for_experiment,
    get_domain_by_id,
    get_domain_by_key,
    get_preflight_conflicts,
    list_bindings_for_experiment,
    list_domains,
    update_domain,
    upsert_binding,
)


def _domain_id_from_request(request: web.Request) -> str | None:
    raw = (
        request.match_info.get("id", "").strip() or request.match_info.get("domain_id", "").strip()
    )
    if not raw:
        return None
    return validate_uuid(raw) if validate_uuid(raw) else None


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = (
        request.match_info.get("id", "").strip()
        or request.match_info.get("experiment_id", "").strip()
    )
    if not raw:
        return None
    return validate_uuid(raw) if validate_uuid(raw) else None


class ConflictDomainCreate(BaseModel):
    key: str
    name: str
    description: str | None = None
    default_policy: str = "mutual_exclusion"

    @field_validator("key")
    @classmethod
    def key_nonempty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 255:
            raise ValueError("key: non-empty, max 255 chars")
        return v

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 255:
            raise ValueError("name: non-empty, max 255 chars")
        return v

    @field_validator("default_policy")
    @classmethod
    def policy_valid(cls, v: str) -> str:
        if v not in ("mutual_exclusion", "bid", "priority"):
            raise ValueError("default_policy must be mutual_exclusion, bid, or priority")
        return v


class ConflictDomainUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    default_policy: str | None = None

    @field_validator("name")
    @classmethod
    def name_opt(cls, v: str | None) -> str | None:
        if v is not None and (not (v := (v or "").strip()) or len(v) > 255):
            raise ValueError("name: non-empty, max 255 chars")
        return v or None

    @field_validator("default_policy")
    @classmethod
    def policy_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in ("mutual_exclusion", "bid", "priority"):
            raise ValueError("default_policy must be mutual_exclusion, bid, or priority")
        return v


class ConflictBindingUpsert(BaseModel):
    domain_id: str
    policy: str | None = None
    priority_tier: int | None = None
    bid_value: float = 0
    is_enabled: bool = True

    @field_validator("domain_id")
    @classmethod
    def domain_id_uuid(cls, v: str) -> str:
        u = validate_uuid(v)
        if not u:
            raise ValueError("Invalid UUID for domain_id")
        return u

    @field_validator("policy")
    @classmethod
    def policy_opt(cls, v: str | None) -> str | None:
        if v is not None and v not in ("mutual_exclusion", "bid", "priority"):
            raise ValueError("policy must be mutual_exclusion, bid, or priority")
        return v

    @field_validator("bid_value")
    @classmethod
    def bid_non_neg(cls, v: float) -> float:
        if v is not None and v < 0:
            raise ValueError("bid_value must be >= 0")
        return v


@docs(
    tags=["Conflict domains"],
    summary="Список конфликтных доменов",
    responses={
        200: {"description": "Список доменов", "schema": ConflictDomainListResponseSchema},
        401: RESPONSES_HTTP_ERROR[401],
    },
)
async def conflict_domains_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    async with Database() as db:
        items = await list_domains(db)
    return web.json_response({"conflict_domains": items})


@docs(
    tags=["Conflict domains"],
    summary="Создать конфликтный домен",
    responses={
        201: {"description": "Домен создан", "schema": ConflictDomainItemSchema},
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        409: RESPONSES_HTTP_ERROR[409],
    },
)
@request_schema(ConflictDomainCreateSchema(), location="json", put_into="data")
@validate.validate(ConflictDomainCreate, require_auth=True)
async def conflict_domains_create(
    request: web.Request, parsed: ConflictDomainCreate
) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    async with Database() as db:
        existing = await get_domain_by_key(db, parsed.key)
        if existing:
            return validate.format_409_conflict(
                request, f"Domain key already exists: {parsed.key}"
            )
        domain = await create_domain(
            db,
            key=parsed.key,
            name=parsed.name,
            description=parsed.description,
            default_policy=parsed.default_policy,
        )
    if not domain:
        return web.json_response(
            {"error": "Invalid default_policy or validation failed"}, status=400
        )
    return web.json_response(domain, status=201)


@docs(
    tags=["Conflict domains"],
    summary="Получить конфликтный домен по ID",
    responses={
        200: {"description": "Домен", "schema": ConflictDomainItemSchema},
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def conflict_domains_get(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    domain_id = _domain_id_from_request(request)
    if not domain_id:
        return validate.format_404_error(request, "Invalid domain id")

    async with Database() as db:
        domain = await get_domain_by_id(db, domain_id)
    if not domain:
        return validate.format_404_error(request, "Conflict domain not found")
    return web.json_response(domain)


@docs(
    tags=["Conflict domains"],
    summary="Обновить конфликтный домен",
    responses={
        200: {"description": "Домен обновлён", "schema": ConflictDomainItemSchema},
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
@request_schema(ConflictDomainUpdateSchema(), location="json", put_into="data")
@validate.validate(ConflictDomainUpdate, require_auth=True)
async def conflict_domains_update(
    request: web.Request, parsed: ConflictDomainUpdate
) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    domain_id = _domain_id_from_request(request)
    if not domain_id:
        return validate.format_404_error(request, "Invalid domain id")

    async with Database() as db:
        domain = await update_domain(
            db,
            domain_id=domain_id,
            name=parsed.name,
            description=parsed.description,
            default_policy=parsed.default_policy,
        )
    if not domain:
        return validate.format_404_error(
            request, "Conflict domain not found or invalid default_policy"
        )
    return web.json_response(domain)


@docs(
    tags=["Conflict domains"],
    summary="Удалить конфликтный домен",
    responses={
        204: {"description": "Домен удалён"},
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def conflict_domains_delete(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    domain_id = _domain_id_from_request(request)
    if not domain_id:
        return validate.format_404_error(request, "Invalid domain id")

    async with Database() as db:
        ok = await delete_domain(db, domain_id)
    if not ok:
        return validate.format_404_error(request, "Conflict domain not found")
    return web.Response(status=204)


@docs(
    tags=["Conflict domains"],
    summary="Список привязок эксперимента к конфликтным доменам",
    responses={
        200: {"description": "Привязки", "schema": ConflictBindingListResponseSchema},
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def experiment_conflict_bindings_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    from functions.experiments import get_experiment_by_id

    if not await get_experiment_by_id(exp_id):
        return validate.format_404_error(request, "Experiment not found")

    async with Database() as db:
        bindings = await list_bindings_for_experiment(db, exp_id)
    return web.json_response({"bindings": bindings})


@docs(
    tags=["Conflict domains"],
    summary="Добавить/обновить привязку эксперимента к домену",
    responses={
        200: {"description": "Привязка создана/обновлена", "schema": ConflictBindingItemSchema},
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
@request_schema(ConflictBindingUpsertSchema(), location="json", put_into="data")
@validate.validate(ConflictBindingUpsert, require_auth=True)
async def experiment_conflict_binding_upsert(
    request: web.Request, parsed: ConflictBindingUpsert
) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    from functions.experiments import get_experiment_by_id

    if not await get_experiment_by_id(exp_id):
        return validate.format_404_error(request, "Experiment not found")

    async with Database() as db:
        domain = await get_domain_by_id(db, parsed.domain_id)
        if not domain:
            return validate.format_404_error(request, "Conflict domain not found")
        binding = await upsert_binding(
            db,
            experiment_id=exp_id,
            domain_id=parsed.domain_id,
            policy=parsed.policy,
            priority_tier=parsed.priority_tier,
            bid_value=parsed.bid_value,
            is_enabled=parsed.is_enabled,
        )
    if not binding:
        return web.json_response({"error": "Invalid policy or validation failed"}, status=400)
    return web.json_response(binding)


@docs(
    tags=["Conflict domains"],
    summary="Удалить привязку эксперимента к домену",
    responses={
        204: {"description": "Привязка удалена"},
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def experiment_conflict_binding_delete(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    domain_id = validate_uuid(request.match_info.get("domain_id", "").strip()) or None
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    if not domain_id:
        return validate.format_404_error(request, "Invalid domain id")

    async with Database() as db:
        ok = await delete_binding(db, experiment_id=exp_id, domain_id=domain_id)
    if not ok:
        return validate.format_404_error(request, "Binding not found")
    return web.Response(status=204)


@docs(
    tags=["Conflict domains"],
    summary="Preflight: с какими running экспериментами будет конфликт при запуске",
    responses={
        200: {
            "description": "Список доменов и конфликтующих экспериментов",
            "schema": ConflictPreflightResponseSchema,
        },
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def experiment_conflict_preflight(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    from functions.experiments import get_experiment_by_id

    if not await get_experiment_by_id(exp_id):
        return validate.format_404_error(request, "Experiment not found")

    async with Database() as db:
        warnings = await get_preflight_conflicts(db, exp_id)
    return web.json_response({"conflict_warnings": warnings})


@docs(
    tags=["Conflict domains"],
    summary="Аудит конфликтов по эксперименту (победитель/проигравший)",
    responses={
        200: {"description": "Записи decision_conflict_log по эксперименту"},
        401: RESPONSES_HTTP_ERROR[401],
        404: RESPONSES_HTTP_ERROR[404],
    },
)
async def experiment_conflict_log(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")

    from functions.experiments import get_experiment_by_id

    if not await get_experiment_by_id(exp_id):
        return validate.format_404_error(request, "Experiment not found")

    limit = 100
    try:
        q = request.url.query.get("limit", "")
        if q:
            limit = max(1, min(500, int(q)))
    except ValueError:
        pass

    async with Database() as db:
        logs = await get_conflict_log_for_experiment(db, exp_id, limit=limit)
    return web.json_response({"decisions": logs})
