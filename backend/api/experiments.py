"""Experiments API for LOTTY A/B Platform."""
from aiohttp import web
from aiohttp_apispec import docs


@docs(
    tags=["Experiments"],
    summary="Создать эксперимент",
    description="Создание нового эксперимента в состоянии черновика.",
    responses={
        201: {"description": "Эксперимент создан"},
        400: {"description": "Некорректный запрос"},
        409: {"description": "Конфликт ключа флага"},
    },
)
async def experiments_create(request: web.Request) -> web.Response:
    return web.json_response({"status": "not_implemented"}, status=501)


@docs(
    tags=["Experiments"],
    summary="Список экспериментов",
    description="Получить список экспериментов с опциональными фильтрами по статусу и флагу.",
    responses={200: {"description": "Список экспериментов"}},
)
async def experiments_list(request: web.Request) -> web.Response:
    return web.json_response({"experiments": [], "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Получить эксперимент",
    description="Получить эксперимент по ID с полной конфигурацией и историей.",
    responses={
        200: {"description": "Данные эксперимента"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_get(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Обновить эксперимент",
    description="Обновить эксперимент. Разрешено только в состоянии черновика.",
    responses={
        200: {"description": "Эксперимент обновлён"},
        400: {"description": "Некорректный запрос или неверное состояние"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_update(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Отправить на ревью",
    description="Перевод эксперимента из черновика в состояние ревью.",
    responses={
        200: {"description": "Отправлено на ревью"},
        400: {"description": "Недопустимый переход состояния"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_submit_review(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Одобрить эксперимент",
    description="Добавить одобрение. Эксперимент становится одобренным при достижении порога.",
    responses={
        200: {"description": "Одобрение записано"},
        400: {"description": "Некорректно или уже одобрен"},
        403: {"description": "Нет прав на одобрение"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_approve(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Запросить изменения",
    description="Вернуть эксперимент в черновик для внесения изменений.",
    responses={
        200: {"description": "Возвращён в черновик"},
        400: {"description": "Недопустимое состояние"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_request_changes(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Отклонить эксперимент",
    description="Отклонить эксперимент. Можно отправить повторно после изменений.",
    responses={
        200: {"description": "Эксперимент отклонён"},
        400: {"description": "Недопустимое состояние"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_reject(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Запустить эксперимент",
    description="Переход из одобренного в состояние запущен.",
    responses={
        200: {"description": "Эксперимент запущен"},
        400: {"description": "Недопустимое состояние или конфликт по флагу"},
        403: {"description": "Нет прав"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_start(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Приостановить эксперимент",
    description="Приостановить запущенный эксперимент. Останавливает распределение вариантов.",
    responses={
        200: {"description": "Эксперимент приостановлен"},
        400: {"description": "Недопустимое состояние"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_pause(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Возобновить эксперимент",
    description="Возобновить приостановленный эксперимент.",
    responses={
        200: {"description": "Эксперимент возобновлён"},
        400: {"description": "Недопустимое состояние или конфликт"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_resume(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="Завершить эксперимент",
    description="Завершить эксперимент с исходом: rollout_winner, rollback или no_effect.",
    responses={
        200: {"description": "Эксперимент завершён"},
        400: {"description": "Недопустимое состояние или отсутствует исход"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_complete(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "status": "not_implemented"}, status=200)


@docs(
    tags=["Experiments"],
    summary="История срабатываний guardrail",
    description="Получить историю срабатываний guardrail для эксперимента.",
    responses={
        200: {"description": "История срабатываний guardrail"},
        404: {"description": "Эксперимент не найден"},
    },
)
async def experiments_guardrail_history(request: web.Request) -> web.Response:
    exp_id = request.match_info.get("id", "")
    return web.json_response({"id": exp_id, "triggers": [], "status": "not_implemented"}, status=200)
