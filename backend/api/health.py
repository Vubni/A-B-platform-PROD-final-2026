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
    responses={200: {}},
)
async def health(request: web.Request) -> web.Response:
    return web.Response(status=200, text="OK")


@docs(
    tags=["Health"],
    summary="Проба готовности",
    responses={
        200: {},
        503: {},
    },
)
async def ready(request: web.Request) -> web.Response:
    if is_ready():
        return web.Response(status=200, text="OK")
    return web.Response(status=503, text="Service Unavailable")
