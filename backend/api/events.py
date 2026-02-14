"""Events API — how product sends 'what happened'."""
from aiohttp import web
from aiohttp_apispec import docs

from api.system_metrics import record_events_submitted


@docs(
    tags=["Events"],
    summary="Отправить пакет событий",
    description=(
        "Принять пакет событий от продукта. Каждое событие связано с decision_id. "
        "Возвращает: количество принятых, дубликатов, отклонённых и ошибки по отклонённым."
    ),
    responses={
        200: {"description": "Пакет обработан. См. счётчики accepted/duplicates/rejected."},
        400: {"description": "Некорректный формат пакета"},
    },
)
async def events_submit(request: web.Request) -> web.Response:
    record_events_submitted(
        accepted=1)  # по пакету; в проде — accepted из ответа
    return web.json_response(
        {
            "accepted": 0,
            "duplicates": 0,
            "rejected": 0,
            "errors": [],
            "status": "not_implemented",
        },
        status=200,
    )


@docs(
    tags=["Events"],
    summary="Список типов событий (каталог)",
    description="Получить каталог типов событий. Админ создаёт/редактирует типы с метаданными и правилами валидации.",
    responses={200: {"description": "Список типов событий"}},
)
async def event_types_list(request: web.Request) -> web.Response:
    return web.json_response({"event_types": [], "status": "not_implemented"}, status=200)


@docs(
    tags=["Events"],
    summary="Создать тип события",
    description="Создать тип события в каталоге (Админ).",
    responses={
        201: {"description": "Тип события создан"},
        400: {"description": "Некорректный запрос"},
        403: {"description": "Только для админа"},
    },
)
async def event_types_create(request: web.Request) -> web.Response:
    return web.json_response({"status": "not_implemented"}, status=501)


@docs(
    tags=["Events"],
    summary="Получить тип события",
    description="Получить тип события по id.",
    responses={
        200: {"description": "Данные типа события"},
        404: {"description": "Не найден"},
    },
)
async def event_types_get(request: web.Request) -> web.Response:
    type_id = request.match_info.get("id", "")
    return web.json_response({"id": type_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Events"],
    summary="Обновить тип события",
    description="Обновить тип события (Админ).",
    responses={
        200: {"description": "Обновлено"},
        400: {"description": "Некорректный запрос"},
        404: {"description": "Не найден"},
    },
)
async def event_types_update(request: web.Request) -> web.Response:
    type_id = request.match_info.get("id", "")
    return web.json_response({"id": type_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Events"],
    summary="Архивировать тип события",
    description="Архивировать тип события (мягкое удаление).",
    responses={
        200: {"description": "Архивировано"},
        404: {"description": "Не найден"},
    },
)
async def event_types_archive(request: web.Request) -> web.Response:
    type_id = request.match_info.get("id", "")
    return web.json_response({"id": type_id, "status": "not_implemented"}, status=200)
