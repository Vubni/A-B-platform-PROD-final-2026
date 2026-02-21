import asyncio
import sys
from pathlib import Path


def _ensure_backend_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    backend_dir = root / "backend"
    sys.path.insert(0, str(backend_dir))


async def main() -> None:
    _ensure_backend_on_path()

    from functions.event_types import create_event_type
    from functions.flags import create_flag
    from functions.metrics import create_metric
    from functions.users import create_approver_group, create_user, get_user_by_email

    admin = await create_user(
        email="admin@test.com",
        first_name="TestAdmin",
        password="admin123",
        role="admin",
    )
    if admin:
        print("Created admin: admin@test.com / admin123")
    else:
        print("Admin already exists or conflict")

    experimenter = await create_user(
        email="experimenter@test.com",
        first_name="TestExperimenter",
        password="exp123",
        role="experimenter",
    )
    if experimenter:
        print("Created experimenter: experimenter@test.com / exp123")
    else:
        experimenter = await get_user_by_email("experimenter@test.com")
        print("Experimenter already exists or conflict")

    viewer = await create_user(
        email="viewer@test.com",
        first_name="TestViewer",
        password="view123",
        role="viewer",
    )
    if viewer:
        print("Created viewer: viewer@test.com / view123")
    else:
        print("Viewer already exists or conflict")

    approver = await create_user(
        email="approver@test.com",
        first_name="TestApprover",
        password="app123",
        role="approver",
    )
    if approver:
        print("Created approver: approver@test.com / app123")
    else:
        approver = await get_user_by_email("approver@test.com")
        print("Approver already exists or conflict")

    flag = await create_flag(
        key="test_feature_flag",
        value_type="string",
        default_value="control",
        description="Flag for API tests",
    )
    if flag:
        print(f"Created flag: test_feature_flag (id={flag.get('id')})")
    else:
        print("Flag test_feature_flag already exists")

    exposure_et, err = await create_event_type(
        key="demo_exposure",
        display_name="Exposure",
        description="Demo exposure event",
    )
    if exposure_et:
        print("Created event type: demo_exposure")
    else:
        print("Event type demo_exposure already exists" if err == "duplicate_key" else f"Event type demo_exposure: {err}")

    click_et, _ = await create_event_type(
        key="demo_click",
        display_name="Click",
        description="Demo click event",
    )
    if click_et:
        print("Created event type: demo_click")
    else:
        print("Event type demo_click already exists or skip")

    exposure_id = None
    if exposure_et and exposure_et.get("id"):
        exposure_id = exposure_et["id"]
    else:
        from functions.event_types import get_event_type_by_key
        existing = await get_event_type_by_key("demo_exposure", active_only=False)
        if existing:
            exposure_id = existing["id"]
    if exposure_id:
        conv_et, conv_err = await create_event_type(
            key="demo_conversion",
            display_name="Conversion",
            description="Demo conversion (requires exposure)",
            requires_show_event_type_id=exposure_id,
        )
        if conv_et:
            print("Created event type: demo_conversion (depends on demo_exposure)")
        else:
            print("Event type demo_conversion already exists" if conv_err == "duplicate_key" else f"demo_conversion: {conv_err}")

    imp, imp_err = await create_metric(
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
    if imp:
        print("Created metric: demo_impressions")
    else:
        print("Metric demo_impressions already exists" if imp_err == "duplicate_key" else f"demo_impressions: {imp_err}")

    conv_metric, c_err = await create_metric(
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
    if conv_metric:
        print("Created metric: demo_conversions")
    else:
        print("Metric demo_conversions already exists" if c_err == "duplicate_key" else f"demo_conversions: {c_err}")

    rate, r_err = await create_metric(
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
    if rate:
        print("Created metric: demo_conversion_rate")
    else:
        print("Metric demo_conversion_rate already exists" if r_err == "duplicate_key" else f"demo_conversion_rate: {r_err}")

    experimenter_id = (experimenter or {}).get("id")
    approver_id = (approver or {}).get("id")
    if experimenter_id and approver_id:
        group = await create_approver_group(
            experimenter_id=experimenter_id,
            min_approvals=1,
            approver_ids=[approver_id],
        )
        if group:
            print("Created approver group for experimenter (min_approvals=1, approver=approver@test.com)")
        else:
            print("Approver group for experimenter already exists")
    else:
        print("Skip approver group: missing experimenter or approver id")

    print("Seed done.")


if __name__ == "__main__":
    asyncio.run(main())

