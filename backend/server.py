import os
import asyncio
from aiohttp import web
from aiohttp_apispec import (
    setup_aiohttp_apispec,
    validation_middleware,
)
import aiohttp_cors

from config import logger
from api import health, flags, experiments, decide, events, reports, users, system_metrics
from database.database import Database


async def _check_readiness(app):
    """Проверка готовности: БД и прочие зависимости. В будущем можно добавить Redis, кеши и т.д."""
    health.set_ready(False)
    try:
        async with Database() as db:
            if db and await db.execute("SELECT 1"):
                health.set_ready(True)
                logger.info("Readiness: все зависимости готовы.")
            else:
                logger.warning("Readiness: БД не отвечает.")
    except Exception as e:
        logger.warning(f"Readiness: ошибка проверки — {e}")


async def startup_readiness(app):
    """Запуск проверки готовности при старте приложения."""
    await _check_readiness(app)


if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(startup_readiness)

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "OPTIONS", "PATCH", "DELETE"],
        )
    })

    setup_aiohttp_apispec(
        app,
        title="LOTTY A/B Platform API",
        version="v1",
        url="/swagger.json",
        swagger_path="/",
        description="A/B экспериментальная платформа.",
        security_definitions={
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "Авторизация токеном",
            }
        },
    )

    prefix = "/api/v1"

    routes = [
        web.get("/health", health.health),
        web.get("/ready", health.ready),
        web.get("/metrics", system_metrics.metrics_export),

        web.get(prefix + "/users", users.users_list),
        web.post(prefix + "/users", users.users_create),
        web.get(prefix + "/users/{id}", users.users_get),
        web.patch(prefix + "/users/{id}", users.users_update),
        web.get(prefix + "/approver-groups", users.approver_groups_list),
        web.put(prefix + "/approver-groups", users.approver_groups_set),

        web.post(prefix + "/flags", flags.flags_create),
        web.get(prefix + "/flags", flags.flags_list),
        web.get(prefix + "/flags/{key}", flags.flags_get),
        web.patch(prefix + "/flags/{key}", flags.flags_update),

        web.post(prefix + "/experiments", experiments.experiments_create),
        web.get(prefix + "/experiments", experiments.experiments_list),
        web.get(prefix + "/experiments/{id}", experiments.experiments_get),
        web.patch(prefix + "/experiments/{id}",
                  experiments.experiments_update),
        web.post(prefix + "/experiments/{id}/submit-review",
                 experiments.experiments_submit_review),
        web.post(prefix + "/experiments/{id}/approve",
                 experiments.experiments_approve),
        web.post(prefix + "/experiments/{id}/request-changes",
                 experiments.experiments_request_changes),
        web.post(prefix + "/experiments/{id}/reject",
                 experiments.experiments_reject),
        web.post(prefix + "/experiments/{id}/start",
                 experiments.experiments_start),
        web.post(prefix + "/experiments/{id}/pause",
                 experiments.experiments_pause),
        web.post(prefix + "/experiments/{id}/resume",
                 experiments.experiments_resume),
        web.post(prefix + "/experiments/{id}/complete",
                 experiments.experiments_complete),
        web.get(prefix + "/experiments/{id}/guardrail-history",
                experiments.experiments_guardrail_history),

        web.post(prefix + "/decide", decide.decide),

        web.post(prefix + "/events", events.events_submit),
        web.get(prefix + "/event-types", events.event_types_list),
        web.post(prefix + "/event-types", events.event_types_create),
        web.get(prefix + "/event-types/{id}", events.event_types_get),
        web.patch(prefix + "/event-types/{id}", events.event_types_update),
        web.delete(prefix + "/event-types/{id}", events.event_types_archive),

        web.get(prefix + "/experiments/{id}/report",
                reports.reports_experiment),
        web.get(prefix + "/metrics", reports.metrics_list),
        web.post(prefix + "/metrics", reports.metrics_create),
    ]

    for route in routes:
        cors.add(app.router.add_route(route.method, route.path, route.handler))

    app.middlewares.insert(0, system_metrics.metrics_middleware)
    app.middlewares.append(validation_middleware)

    logger.info("LOTTY A/B Platform API started.")
    web.run_app(
        app,
        host=os.environ.get("INSTANCE_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 80)),
    )
