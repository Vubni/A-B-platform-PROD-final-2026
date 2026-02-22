import os

import aiohttp_cors
from aiohttp import web
from aiohttp_apispec import (
    setup_aiohttp_apispec,
    validation_middleware,
)

from api import (
    auth,
    autopilot_ramp_api,
    conflict_domains,
    decide,
    events,
    experiments,
    flags,
    guardrails,
    health,
    learnings,
    reports,
    system_metrics,
    users,
)
from config import logger
from database.database import Database
from database.functions import init_reference_data
from functions.users import create_user


async def init_first_admin():
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        return
    first_name = os.environ.get("ADMIN_FIRST_NAME", "Admin")
    admin = await create_user(email=email, first_name=first_name, password=password, role="admin")
    if admin:
        logger.info(f"Создан первый админ: {email}")


async def check_readiness(app):
    health.set_ready(False)
    try:
        async with Database() as db:
            if db and await db.execute("SELECT 1"):
                await init_reference_data()
                await init_first_admin()
                health.set_ready(True)
                logger.info("Readiness: все зависимости и данные готовы.")
            else:
                logger.warning("Readiness: БД не отвечает.")
    except Exception as e:
        logger.warning(f"Readiness: ошибка проверки — {e}")


if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(check_readiness)

    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods=["GET", "POST", "OPTIONS", "PATCH", "DELETE"],
            )
        },
    )

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
        web.post(prefix + "/auth", auth.auth_login),
        web.get(prefix + "/users", users.users_list),
        web.post(prefix + "/users", users.users_create),
        web.get(prefix + "/users/{id}", users.users_get),
        web.patch(prefix + "/users/{id}", users.users_update),
        web.get(prefix + "/approver-groups", users.approver_groups_list),
        web.post(prefix + "/approver-groups", users.approver_groups_create),
        web.patch(prefix + "/approver-groups/{id}", users.approver_groups_update),

        web.post(prefix + "/flags", flags.flags_create),
        web.get(prefix + "/flags", flags.flags_list),
        web.get(prefix + "/flags/{key}", flags.flags_get),
        web.patch(prefix + "/flags/{key}", flags.flags_update),

        web.post(prefix + "/experiments", experiments.experiments_create),
        web.get(prefix + "/experiments", experiments.experiments_list),
        web.get(prefix + "/experiments/{id}", experiments.experiments_get),
        web.patch(prefix + "/experiments/{id}", experiments.experiments_update),
        web.patch(prefix + "/experiments/{id}/status", experiments.experiments_update_status),
        web.post(prefix + "/experiments/{id}/complete", experiments.experiments_complete),
        web.post(prefix + "/experiments/{id}/variants", experiments.experiments_variant_create),
        web.patch(
            prefix + "/experiments/{id}/variants/{variant_id}",
            experiments.experiments_variant_update,
        ),
        web.delete(
            prefix + "/experiments/{id}/variants/{variant_id}",
            experiments.experiments_variant_delete,
        ),
        web.get(
            prefix + "/experiments/{id}/guardrail-history",
            experiments.experiments_guardrail_history,
        ),
        web.get(prefix + "/experiments/{id}/ramp-plan", autopilot_ramp_api.ramp_plan_get),
        web.put(prefix + "/experiments/{id}/ramp-plan", autopilot_ramp_api.ramp_plan_put),
        web.delete(prefix + "/experiments/{id}/ramp-plan", autopilot_ramp_api.ramp_plan_delete),
        web.get(prefix + "/experiments/{id}/ramp-state", autopilot_ramp_api.ramp_state_get),
        web.post(prefix + "/experiments/{id}/ramp-start", autopilot_ramp_api.ramp_start_post),
        web.patch(prefix + "/experiments/{id}/ramp-mode", autopilot_ramp_api.ramp_mode_patch),
        web.post(
            prefix + "/experiments/{id}/ramp-override", autopilot_ramp_api.ramp_override_post
        ),
        web.get(
            prefix + "/experiments/{id}/ramp-decision-log",
            autopilot_ramp_api.ramp_decision_log_get,
        ),

        web.get(prefix + "/guardrails", guardrails.guardrails_list),
        web.get(prefix + "/guardrails/{metric_key}", guardrails.guardrails_get),
        web.post(prefix + "/guardrails", guardrails.guardrails_upsert),
        web.delete(prefix + "/guardrails/{metric_key}", guardrails.guardrails_delete),

        web.get(prefix + "/conflict-domains", conflict_domains.conflict_domains_list),
        web.post(prefix + "/conflict-domains", conflict_domains.conflict_domains_create),
        web.get(prefix + "/conflict-domains/{id}", conflict_domains.conflict_domains_get),
        web.patch(prefix + "/conflict-domains/{id}", conflict_domains.conflict_domains_update),
        web.delete(prefix + "/conflict-domains/{id}", conflict_domains.conflict_domains_delete),
        web.get(
            prefix + "/experiments/{id}/conflict-bindings",
            conflict_domains.experiment_conflict_bindings_list,
        ),
        web.post(
            prefix + "/experiments/{id}/conflict-bindings",
            conflict_domains.experiment_conflict_binding_upsert,
        ),
        web.delete(
            prefix + "/experiments/{id}/conflict-bindings/{domain_id}",
            conflict_domains.experiment_conflict_binding_delete,
        ),
        web.get(
            prefix + "/experiments/{id}/conflict-preflight",
            conflict_domains.experiment_conflict_preflight,
        ),
        web.get(
            prefix + "/experiments/{id}/conflict-log", conflict_domains.experiment_conflict_log
        ),

        web.post(prefix + "/decide", decide.decide),

        web.post(prefix + "/events", events.events_submit),
        web.get(prefix + "/event-types", events.event_types_list),
        web.post(prefix + "/event-types", events.event_types_create),
        web.get(prefix + "/event-types/{id}", events.event_types_get),
        web.patch(prefix + "/event-types/{id}", events.event_types_update),
        web.delete(prefix + "/event-types/{id}", events.event_types_archive),

        web.get(prefix + "/experiments/{id}/report", reports.reports_experiment),
        web.get(prefix + "/learnings", learnings.learnings_list),
        web.get(prefix + "/learnings/{id}", learnings.learnings_get),
        web.get(prefix + "/learnings/{id}/audit", learnings.learnings_audit),
        web.get(prefix + "/learnings/{id}/similar", learnings.learnings_similar),
        web.get(prefix + "/experiments/{id}/learning", learnings.learning_by_experiment_get),
        web.put(prefix + "/experiments/{id}/learning", learnings.learning_upsert_for_experiment),
        web.get(prefix + "/metrics", reports.metrics_list),
        web.get(prefix + "/metrics/{key}", reports.metrics_get),
        web.post(prefix + "/metrics", reports.metrics_create),
        web.patch(prefix + "/metrics/{key}", reports.metrics_update),
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
