"""Feature Flags API for LOTTY A/B Platform."""
from aiohttp import web
from aiohttp_apispec import docs


@docs(
    tags=["Feature Flags"],
    summary="Создать feature flag",
    description="Создание нового feature flag с ключом, типом значения и значением по умолчанию.",
    responses={
        201: {"description": "Флаг создан"},
        400: {"description": "Некорректный запрос"},
        409: {"description": "Флаг с таким ключом уже существует"},
    },
)
async def flags_create(request: web.Request) -> web.Response:
    return web.json_response({"status": "not_implemented"}, status=501)


@docs(
    tags=["Feature Flags"],
    summary="Список feature flags",
    description="Получить список всех feature flags с опциональными фильтрами.",
    responses={200: {"description": "Список флагов"}},
)
async def flags_list(request: web.Request) -> web.Response:
    return web.json_response({"flags": [], "status": "not_implemented"}, status=200)


@docs(
    tags=["Feature Flags"],
    summary="Получить feature flag",
    description="Получить feature flag по ключу.",
    responses={
        200: {"description": "Данные флага"},
        404: {"description": "Флаг не найден"},
    },
)
async def flags_get(request: web.Request) -> web.Response:
    key = request.match_info.get("key", "")
    return web.json_response({"key": key, "status": "not_implemented"}, status=200)


@docs(
    tags=["Feature Flags"],
    summary="Обновить значение по умолчанию feature flag",
    description="Обновить только значение по умолчанию существующего флага. Варианты и эксперименты не меняются.",
    responses={
        200: {"description": "Флаг обновлён"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Флаг не найден"},
    },
)
async def flags_update(request: web.Request) -> web.Response:
    key = request.match_info.get("key", "")
    return web.json_response({"key": key, "status": "not_implemented"}, status=200)
