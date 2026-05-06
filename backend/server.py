import asyncio
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
from config import EVENTS_USE_KAFKA, KAFKA_BOOTSTRAP_SERVERS, logger
from database.database import Database
from database.functions import init_reference_data
from database.seed_demo import seed_demo_data
from functions.users import create_approver_group, create_user, get_user_by_email


async def init_first_admin():
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        return
    first_name = os.environ.get("ADMIN_FIRST_NAME", "Admin")
    admin = await create_user(email=email, first_name=first_name, password=password, role="admin")
    if admin:
        logger.info(f"Создан первый админ: {email}")


DEMO_USERS = [
    ("admin@test.com", "TestAdmin", "admin123", "admin"),
    ("experimenter@test.com", "TestExperimenter", "exp123", "experimenter"),
    ("viewer@test.com", "TestViewer", "view123", "viewer"),
    ("approver@test.com", "TestApprover", "app123", "approver"),
]


async def init_demo_users():
    if not os.environ.get("SEED_DEMO_USERS", "").strip():
        return
    for email, first_name, password, role in DEMO_USERS:
        user = await create_user(email=email, first_name=first_name, password=password, role=role)
        if user:
            logger.info(f"Демо-пользователь: {email} ({role})")
    experimenter = await get_user_by_email("experimenter@test.com")
    approver = await get_user_by_email("approver@test.com")
    if experimenter and approver:
        group = await create_approver_group(
            experimenter_id=str(experimenter["id"]),
            min_approvals=1,
            approver_ids=[str(approver["id"])],
        )
        if group:
            logger.info("Демо: группа аппруверов для experimenter создана")
    await seed_demo_data()


async def check_readiness(app):
    health.set_ready(False)
    for attempt in range(1, 31):
        try:
            async with Database() as db:
                if db and await db.execute("SELECT 1"):
                    await init_reference_data()
                    await init_first_admin()
                    await init_demo_users()
                    health.set_ready(True)
                    logger.info("Readiness: все зависимости и данные готовы.")
                    return
                logger.warning("Readiness: БД не отвечает.")
        except Exception as e:
            logger.warning(f"Readiness: ошибка проверки — {e}")
        await asyncio.sleep(1)
        logger.info("Readiness: повторная проверка БД %s/30.", attempt)


async def _start_kafka_consumer_once(app: web.Application) -> bool:
    from kafka_events import ensure_topic, start_consumer

    if not await ensure_topic():
        return False
    task = await start_consumer()
    if not task:
        return False
    app["kafka_consumer_task"] = task
    logger.info("Kafka: приём событий через очередь включён.")
    return True


async def _kafka_retry_loop(app: web.Application) -> None:
    if not EVENTS_USE_KAFKA or not KAFKA_BOOTSTRAP_SERVERS:
        return
    while True:
        await asyncio.sleep(10)
        task = app.get("kafka_consumer_task")
        if task is not None and not task.done():
            continue
        if task is not None and task.done():
            app["kafka_consumer_task"] = None
        try:
            if await _start_kafka_consumer_once(app):
                break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("Kafka retry: %s", e)


async def start_kafka_if_enabled(app: web.Application) -> None:
    if not EVENTS_USE_KAFKA or not KAFKA_BOOTSTRAP_SERVERS:
        return

    for _attempt in range(5):
        if await _start_kafka_consumer_once(app):
            break
        await asyncio.sleep(2)
    else:
        logger.warning(
            "Kafka: топик недоступен после нескольких попыток, повторные попытки в фоне."
        )
        app["kafka_retry_task"] = asyncio.create_task(_kafka_retry_loop(app))


async def cleanup_kafka(app: web.Application) -> None:
    from kafka_events import stop_consumer, stop_producer

    retry_task = app.get("kafka_retry_task")
    if retry_task is not None and not retry_task.done():
        retry_task.cancel()
        try:
            await retry_task
        except asyncio.CancelledError:
            pass
        app["kafka_retry_task"] = None
    await stop_consumer()
    await stop_producer()


if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(check_readiness)
    app.on_startup.append(start_kafka_if_enabled)
    app.on_cleanup.append(cleanup_kafka)

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
        security_definitions={
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
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
        web.patch(
            prefix + "/approver-groups/{id}", users.approver_groups_update),
        web.post(prefix + "/flags", flags.flags_create),
        web.get(prefix + "/flags", flags.flags_list),
        web.get(prefix + "/flags/{key}", flags.flags_get),
        web.patch(prefix + "/flags/{key}", flags.flags_update),
        web.post(prefix + "/experiments", experiments.experiments_create),
        web.get(prefix + "/experiments", experiments.experiments_list),
        web.get(prefix + "/experiments/{id}", experiments.experiments_get),
        web.patch(prefix + "/experiments/{id}",
                  experiments.experiments_update),
        web.patch(prefix + "/experiments/{id}/status",
                  experiments.experiments_update_status),
        web.post(prefix + "/experiments/{id}/complete",
                 experiments.experiments_complete),
        web.post(prefix + "/experiments/{id}/archive",
                 experiments.experiments_archive),
        web.post(prefix + "/experiments/{id}/variants",
                 experiments.experiments_variant_create),
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
        web.get(prefix + "/experiments/{id}/ramp-plan",
                autopilot_ramp_api.ramp_plan_get),
        web.put(prefix + "/experiments/{id}/ramp-plan",
                autopilot_ramp_api.ramp_plan_put),
        web.delete(
            prefix + "/experiments/{id}/ramp-plan", autopilot_ramp_api.ramp_plan_delete),
        web.get(prefix + "/experiments/{id}/ramp-state",
                autopilot_ramp_api.ramp_state_get),
        web.post(prefix + "/experiments/{id}/ramp-start",
                 autopilot_ramp_api.ramp_start_post),
        web.patch(
            prefix + "/experiments/{id}/ramp-mode", autopilot_ramp_api.ramp_mode_patch),
        web.post(
            prefix +
            "/experiments/{id}/ramp-override", autopilot_ramp_api.ramp_override_post
        ),
        web.get(
            prefix + "/experiments/{id}/ramp-decision-log",
            autopilot_ramp_api.ramp_decision_log_get,
        ),
        web.get(prefix + "/guardrails", guardrails.guardrails_list),
        web.get(prefix + "/guardrails/{metric_key}",
                guardrails.guardrails_get),
        web.post(prefix + "/guardrails", guardrails.guardrails_upsert),
        web.delete(
            prefix + "/guardrails/{metric_key}", guardrails.guardrails_delete),
        web.get(prefix + "/conflict-domains",
                conflict_domains.conflict_domains_list),
        web.post(prefix + "/conflict-domains",
                 conflict_domains.conflict_domains_create),
        web.get(prefix + "/conflict-domains/{id}",
                conflict_domains.conflict_domains_get),
        web.patch(
            prefix + "/conflict-domains/{id}", conflict_domains.conflict_domains_update),
        web.delete(
            prefix + "/conflict-domains/{id}", conflict_domains.conflict_domains_delete),
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
            prefix +
            "/experiments/{id}/conflict-log", conflict_domains.experiment_conflict_log
        ),
        web.post(prefix + "/decide", decide.decide),
        web.post(prefix + "/events", events.events_submit),
        web.get(prefix + "/event-types", events.event_types_list),
        web.post(prefix + "/event-types", events.event_types_create),
        web.get(prefix + "/event-types/{id}", events.event_types_get),
        web.patch(prefix + "/event-types/{id}", events.event_types_update),
        web.delete(prefix + "/event-types/{id}", events.event_types_archive),
        web.get(prefix + "/experiments/{id}/report",
                reports.reports_experiment),
        web.get(prefix + "/learnings", learnings.learnings_list),
        web.get(prefix + "/learnings/{id}", learnings.learnings_get),
        web.get(prefix + "/learnings/{id}/audit", learnings.learnings_audit),
        web.get(prefix + "/learnings/{id}/similar",
                learnings.learnings_similar),
        web.get(prefix + "/experiments/{id}/learning",
                learnings.learning_by_experiment_get),
        web.put(prefix + "/experiments/{id}/learning",
                learnings.learning_upsert_for_experiment),
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
        port=int(os.environ.get("PORT", 8080)),
    )
