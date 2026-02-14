"""Reports API — how product/analyst sees experiment results."""
from aiohttp import web
from aiohttp_apispec import docs

from api.system_metrics import record_report_requested


@docs(
    tags=["Reports"],
    summary="Отчёт по эксперименту",
    description=(
        "Получить отчёт по эксперименту: метрики по вариантам, временное окно, "
        "целевая метрика, guardrail. Query params: start, end для временного окна."
    ),
    responses={
        200: {"description": "Отчёт с метриками по вариантам"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def reports_experiment(request: web.Request) -> web.Response:
    record_report_requested()
    exp_id = request.match_info.get("id", "")
    return web.json_response(
        {
            "experiment_id": exp_id,
            "variants": [],
            "metrics": [],
            "status": "not_implemented",
        },
        status=200,
    )


@docs(
    tags=["Reports"],
    summary="Каталог метрик",
    description="Получить каталог настраиваемых метрик (Админ).",
    responses={200: {"description": "Список метрик"}},
)
async def metrics_list(request: web.Request) -> web.Response:
    return web.json_response({"metrics": [], "status": "not_implemented"}, status=200)


@docs(
    tags=["Reports"],
    summary="Создать метрику",
    description="Создать метрику в каталоге (Админ). Задаёт правила вычисления из событий.",
    responses={
        201: {"description": "Метрика создана"},
        400: {"description": "Некорректный запрос"},
    },
)
async def metrics_create(request: web.Request) -> web.Response:
    return web.json_response({"status": "not_implemented"}, status=501)
