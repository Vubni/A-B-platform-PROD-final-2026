from config import logger
from functions.event_types import create_event_type, get_event_type_by_key
from functions.flags import create_flag
from functions.metrics import create_metric


async def seed_demo_data() -> None:
    flag = await create_flag(
        key="test_feature_flag",
        value_type="string",
        default_value="control",
        description="Flag for API tests and reviewer demos",
    )
    if flag:
        logger.info("Демо-сид: флаг test_feature_flag создан")

    await create_event_type(
        key="demo_exposure",
        display_name="Exposure",
        description="Demo exposure event",
    )
    await create_event_type(
        key="demo_click",
        display_name="Click",
        description="Demo click event",
    )
    exposure = await get_event_type_by_key("demo_exposure", active_only=False)
    if exposure:
        await create_event_type(
            key="demo_conversion",
            display_name="Conversion",
            description="Demo conversion (requires exposure)",
            requires_show_event_type_id=exposure["id"],
        )

    await create_metric(
        key="demo_impressions",
        name="Demo impressions",
        description="Count of demo_exposure events",
        aggregation_rule={
            "kind": "count_events",
            "event_type_key": "demo_exposure",
            "aggregation_unit": "subject",
        },
        attribution_rule={"requires_decision": True},
        event_expectations={"demo_exposure": "higher"},
        unit="events",
    )
    await create_metric(
        key="demo_conversions",
        name="Demo conversions",
        description="Count of demo_conversion events",
        aggregation_rule={
            "kind": "count_events",
            "event_type_key": "demo_conversion",
            "aggregation_unit": "subject",
        },
        attribution_rule={"requires_decision": True},
        event_expectations={"demo_conversion": "higher"},
        unit="events",
    )
    await create_metric(
        key="demo_conversion_rate",
        name="Demo conversion rate",
        description="demo_conversions / demo_impressions",
        aggregation_rule={
            "kind": "ratio",
            "numerator_metric_key": "demo_conversions",
            "denominator_metric_key": "demo_impressions",
            "aggregation_unit": "subject",
        },
        attribution_rule={"requires_decision": True},
        unit="ratio",
    )
    logger.info("Демо-сид: флаг, типы событий и метрики готовы")
