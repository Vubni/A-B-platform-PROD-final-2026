"""Runtime Decide API — how product gets 'what to show' for a user."""
from aiohttp import web
from aiohttp_apispec import docs, request_schema

from api.system_metrics import record_decide
from docs.schems import DecideRequestSchema, DecideResponseSchema


@docs(
    tags=["Runtime Decide"],
    summary="Получить значения флагов для субъекта",
    description=(
        "API решений: возвращает значения для запрошенных feature flags для данного субъекта. "
        "Продукт передаёт subject_id, атрибуты и список ключей флагов. "
        "Возвращает value, decision_id (для атрибуции событий), experiment_id и variant при наличии."
    ),
    responses={
        200: {"description": "Решения для каждого запрошенного флага", "schema": DecideResponseSchema},
        400: {"description": "Некорректный запрос"},
    },
)
@request_schema(DecideRequestSchema(), location="json", put_into="data")
async def decide(request: web.Request) -> web.Response:
    record_decide()
    return web.json_response(
        {
            "decisions": {},
            "status": "not_implemented",
        },
        status=200,
    )
