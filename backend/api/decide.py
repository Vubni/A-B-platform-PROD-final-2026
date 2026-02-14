"""Runtime Decide API — how product gets 'what to show' for a user."""
from aiohttp import web
from aiohttp_apispec import docs

from api.system_metrics import record_decide


@docs(
    tags=["Runtime Decide"],
    summary="Получить значения флагов для субъекта",
    description=(
        "API решений: возвращает значения для запрошенных feature flags для данного субъекта. "
        "Продукт передаёт subject_id, атрибуты и список ключей флагов. "
        "Возвращает value, decision_id (для атрибуции событий), experiment_id и variant при наличии."
    ),
    responses={
        200: {"description": "Решения для каждого запрошенного флага"},
        400: {"description": "Некорректный запрос"},
    },
)
async def decide(request: web.Request) -> web.Response:
    record_decide()
    return web.json_response(
        {
            "decisions": {},
            "status": "not_implemented",
        },
        status=200,
    )
