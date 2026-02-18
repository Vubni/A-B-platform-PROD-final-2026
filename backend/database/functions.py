import json
from typing import Any

from config import logger
from database.database import Database


DEFAULT_METRICS: list[dict[str, Any]] = [
    {
        "key": "impressions",
        "name": "Число показов",
        "description": "Количество показов (exposure) в выбранном окне отчёта.",
        "unit": "events",
        "aggregation_rule": {
            "kind": "count_events",
            "event_type_key": "exposure",
            "aggregation_unit": "subject",
        },
        "attribution_rule": {
            "requires_decision": True,
        },
    },
    {
        "key": "conversions",
        "name": "Число конверсий",
        "description": "Количество конверсий (conversion) в выбранном окне отчёта.",
        "unit": "events",
        "aggregation_rule": {
            "kind": "count_events",
            "event_type_key": "conversion",
            "aggregation_unit": "subject",
        },
        "attribution_rule": {
            "requires_decision": True,
        },
    },
    {
        "key": "conversion_rate",
        "name": "Доля конверсий",
        "description": "Отношение конверсий к показам (conversions / impressions).",
        "unit": "ratio",
        "aggregation_rule": {
            "kind": "ratio",
            "numerator_metric_key": "conversions",
            "denominator_metric_key": "impressions",
            "aggregation_unit": "subject",
        },
        "attribution_rule": {
            "requires_decision": True,
        },
    },
    {
        "key": "errors",
        "name": "Число ошибок",
        "description": "Количество событий ошибок за интервал отчёта.",
        "unit": "events",
        "aggregation_rule": {
            "kind": "count_events",
            "event_type_key": "error",
            "aggregation_unit": "event",
        },
        "attribution_rule": {
            "requires_decision": False,
        },
    },
    {
        "key": "error_rate",
        "name": "Доля ошибок",
        "description": "Отношение количества ошибок к числу показов (errors / impressions).",
        "unit": "ratio",
        "aggregation_rule": {
            "kind": "ratio",
            "numerator_metric_key": "errors",
            "denominator_metric_key": "impressions",
            "aggregation_unit": "subject",
        },
        "attribution_rule": {
            "requires_decision": False,
        },
    },
    {
        "key": "latency_avg",
        "name": "Средняя задержка",
        "description": "Средняя задержка по событиям с длительностью в payload.duration_ms.",
        "unit": "ms",
        "aggregation_rule": {
            "kind": "avg",
            "event_type_key": "latency",
            "value_path": "payload.duration_ms",
            "aggregation_unit": "event",
        },
        "attribution_rule": {
            "requires_decision": False,
        },
    },
    {
        "key": "latency_p95",
        "name": "95-й перцентиль задержки",
        "description": "95-й перцентиль задержки по событиям с длительностью в payload.duration_ms.",
        "unit": "ms",
        "aggregation_rule": {
            "kind": "percentile",
            "percentile": 95,
            "event_type_key": "latency",
            "value_path": "payload.duration_ms",
            "aggregation_unit": "event",
        },
        "attribution_rule": {
            "requires_decision": False,
        },
    },
]


async def init_metric_catalog_defaults():
    async with Database() as db:
        if not db:
            logger.error("init_metric_catalog_defaults: нет соединения с БД")
            return

        for metric in DEFAULT_METRICS:
            try:
                await db.execute(
                    """
                    INSERT INTO metric_catalog (key, name, description, aggregation_rule, attribution_rule, unit)
                    VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)
                    ON CONFLICT (key) DO UPDATE
                    SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        aggregation_rule = EXCLUDED.aggregation_rule,
                        attribution_rule = EXCLUDED.attribution_rule,
                        unit = EXCLUDED.unit,
                        updated_at = NOW()
                    """,
                    (
                        metric["key"],
                        metric.get("name"),
                        metric.get("description"),
                        json.dumps(metric.get("aggregation_rule") or {}),
                        json.dumps(metric.get("attribution_rule") or {}),
                        metric.get("unit"),
                    ),
                )
            except Exception as e:
                logger.error(f"Не удалось инициализировать метрику {metric.get('key')}: {e}")


async def init_reference_data():
    await init_metric_catalog_defaults()

