from aiohttp import web
from aiohttp_apispec import docs

_ready = False


def set_ready(value: bool) -> None:
    global _ready
    _ready = value


def is_ready() -> bool:
    return _ready


@docs(
    tags=["Health"],
    summary="Проба живости",
    description="Возвращает 200, когда процесс запущен. Не проверяет зависимости.",
    responses={200: {"description": "Процесс запущен"}},
)
async def health(request: web.Request) -> web.Response:
    return web.Response(status=200, text="OK")


@docs(
    tags=["Health"],
    summary="Проба готовности",
    description="Возвращает 200, когда приложение готово принимать запросы. Возвращает 503, пока критичные зависимости (БД и др.) не готовы.",
    responses={
        200: {"description": "Готов к приёму запросов"},
        503: {"description": "Зависимости не готовы"},
    },
)
async def ready(request: web.Request) -> web.Response:
    if is_ready():
        return web.Response(status=200, text="OK")
    return web.Response(status=503, text="Service Unavailable")
