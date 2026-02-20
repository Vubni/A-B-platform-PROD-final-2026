import os
import sys
import uuid
from pathlib import Path

import pytest
from aiohttp import ClientSession

_tests_dir = Path(__file__).resolve().parent
_project_root = _tests_dir.parent
_backend_dir = _project_root / "backend"
if _backend_dir.exists() and str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:80")


TEST_SECTIONS = {
    "test_health.py": "Health",
    "test_users_api.py": "Users",
    "test_flags_api.py": "Flags",
    "test_experiments_api.py": "Experiments",
    "test_experiment_validation.py": "Experiments (validation)",
    "test_decide_api.py": "Decide",
    "test_events_api.py": "Events",
    "test_reports_api.py": "Reports",
}


def _section_for_nodeid(nodeid: str) -> str:
    part = nodeid.split("::")[0]
    basename = part.split("/")[-1] if "/" in part else part.replace(".py", "")
    return TEST_SECTIONS.get(basename, basename)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "test_events_api" in item.nodeid:
            if "event_types" in item.nodeid:
                item.add_marker(pytest.mark.event_types)
            elif "events_submit" in item.nodeid:
                item.add_marker(pytest.mark.events_submit)


def pytest_report_collectionfinish(config, start_path, items):
    groups = {}
    for item in items:
        section = _section_for_nodeid(item.nodeid)
        groups.setdefault(section, []).append(item.nodeid.split("::")[-1])
    order = list(TEST_SECTIONS.values()) + [s for s in sorted(groups) if s not in TEST_SECTIONS.values()]
    lines = []
    for section in order:
        if section in groups:
            lines.append(f"  {section}: {len(groups[section])} tests")
    for section in sorted(groups):
        if section not in order:
            lines.append(f"  {section}: {len(groups[section])} tests")
    if lines:
        return ["\nTest groups:", "\n".join(lines), ""]
    return []


_last_section = [None]


def pytest_runtest_setup(item):
    section = _section_for_nodeid(item.nodeid)
    if _last_section[0] != section:
        _last_section[0] = section
        reporter = item.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.ensure_newline()
            reporter.write_line(f"--- {section} ---")


@pytest.fixture
def base_url():
    return BASE_URL.rstrip("/")


@pytest.fixture
async def http_session():
    async with ClientSession() as session:
        yield session


async def _login(session: ClientSession, base_url: str, email: str, password: str):
    url = f"{base_url}/api/v1/auth"
    payload = {"email": email, "password": password}
    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"Login failed {resp.status}: {text}")
        data = await resp.json()
        return data["token"], data.get("user", {})


@pytest.fixture
async def admin_token(http_session, base_url):
    token, _ = await _login(http_session, base_url, "admin@test.com", "admin123")
    return token


@pytest.fixture
async def experimenter_token(http_session, base_url):
    token, _ = await _login(http_session, base_url, "experimenter@test.com", "exp123")
    return token


@pytest.fixture
async def auth_headers_experimenter(experimenter_token):
    return {"Authorization": f"Bearer {experimenter_token}"}


@pytest.fixture
async def auth_headers_admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
async def viewer_token(http_session, base_url):
    token, _ = await _login(http_session, base_url, "viewer@test.com", "view123")
    return token


@pytest.fixture
async def auth_headers_viewer(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest.fixture
async def approver_token(http_session, base_url):
    token, _ = await _login(http_session, base_url, "approver@test.com", "app123")
    return token


@pytest.fixture
async def auth_headers_approver(approver_token):
    return {"Authorization": f"Bearer {approver_token}"}


@pytest.fixture
async def flag_id(http_session, base_url, auth_headers_admin):
    url = f"{base_url}/api/v1/flags/test_feature_flag"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["id"]
    url = f"{base_url}/api/v1/flags"
    async with http_session.post(
        url,
        headers=auth_headers_admin,
        json={
            "key": "test_feature_flag",
            "value_type": "string",
            "default_value": "control",
            "description": "For tests",
        },
    ) as resp:
        if resp.status in (200, 201):
            data = await resp.json()
            return data["id"]
    pytest.skip("Could not get or create test flag")


@pytest.fixture
async def linked_event_types_metrics_experiment(
    http_session,
    base_url,
    auth_headers_admin,
    auth_headers_experimenter,
):
    suffix = uuid.uuid4().hex[:8]
    et_url = f"{base_url}/api/v1/event-types"
    event_keys = {}
    for key_slug, display in [("exposure", "Exposure"), ("click", "Click"), ("conversion", "Conversion")]:
        key = f"test_et_{key_slug}_{suffix}"
        async with http_session.post(
            et_url,
            headers=auth_headers_admin,
            json={"key": key, "display_name": display},
        ) as r:
            if r.status not in (200, 201):
                pytest.skip(f"Could not create event type {key}: {(await r.text())}")
        event_keys[key_slug] = key

    metrics_url = f"{base_url}/api/v1/metrics"
    metric_keys = {}
    key_imp = f"test_impressions_{suffix}"
    async with http_session.post(
        metrics_url,
        headers=auth_headers_experimenter,
        json={
            "key": key_imp,
            "name": "Test impressions",
            "description": "Count exposure events",
            "aggregation_rule": {
                "kind": "count_events",
                "event_type_key": event_keys["exposure"],
                "aggregation_unit": "subject",
            },
            "attribution_rule": {"requires_decision": True},
            "event_expectations": {event_keys["exposure"]: "higher"},
            "unit": "events",
        },
    ) as r:
        if r.status not in (200, 201):
            pytest.skip(f"Could not create metric {key_imp}: {(await r.text())}")
    metric_keys["impressions"] = key_imp

    key_conv = f"test_conversions_{suffix}"
    async with http_session.post(
        metrics_url,
        headers=auth_headers_experimenter,
        json={
            "key": key_conv,
            "name": "Test conversions",
            "description": "Count conversion events",
            "aggregation_rule": {
                "kind": "count_events",
                "event_type_key": event_keys["conversion"],
                "aggregation_unit": "subject",
            },
            "attribution_rule": {"requires_decision": True},
            "event_expectations": {event_keys["conversion"]: "higher"},
            "unit": "events",
        },
    ) as r:
        if r.status not in (200, 201):
            pytest.skip(f"Could not create metric {key_conv}: {(await r.text())}")
    metric_keys["conversions"] = key_conv

    key_rate = f"test_conversion_rate_{suffix}"
    async with http_session.post(
        metrics_url,
        headers=auth_headers_experimenter,
        json={
            "key": key_rate,
            "name": "Test conversion rate",
            "description": "Conversions / impressions",
            "aggregation_rule": {
                "kind": "ratio",
                "numerator_metric_key": key_conv,
                "denominator_metric_key": key_imp,
                "aggregation_unit": "subject",
            },
            "attribution_rule": {"requires_decision": True},
            "unit": "ratio",
        },
    ) as r:
        if r.status not in (200, 201):
            pytest.skip(f"Could not create metric {key_rate}: {(await r.text())}")
    metric_keys["conversion_rate"] = key_rate

    flags_url = f"{base_url}/api/v1/flags"
    flag_key = f"test_linked_flag_{suffix}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={
            "key": flag_key,
            "value_type": "string",
            "default_value": "control",
        },
    ) as r:
        if r.status not in (200, 201):
            pytest.skip(f"Could not create flag: {(await r.text())}")
        flag_data = await r.json()
    flag_id = flag_data["id"]

    exp_url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": flag_id,
        "name": f"Linked experiment {suffix}",
        "audience_fraction": 1.0,
        "metrics": [
            {"metric_key": key_rate, "metric_type": "primary"},
            {"metric_key": key_imp, "metric_type": "auxiliary"},
            {"metric_key": key_conv, "metric_type": "guardrail"},
        ],
    }
    async with http_session.post(
        exp_url,
        headers=auth_headers_experimenter,
        json=payload,
    ) as r:
        if r.status != 201:
            pytest.skip(f"Could not create experiment with metrics: {(await r.text())}")
        exp_data = await r.json()
    exp_id = exp_data["id"]

    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    for name, value, weight, is_control in [
        ("control", "c", 0.5, True),
        ("treatment", "t", 0.5, False),
    ]:
        async with http_session.post(
            var_url,
            headers=auth_headers_experimenter,
            json={
                "variant_name": name,
                "variant_value": value,
                "weight": weight,
                "is_control": is_control,
            },
        ) as vr:
            if vr.status != 201:
                pytest.skip(f"Could not add variant {name}: {vr.status} {(await vr.text())}")

    return {
        "event_type_keys": event_keys,
        "metric_keys": metric_keys,
        "flag_id": flag_id,
        "flag_key": flag_key,
        "experiment_id": exp_id,
        "suffix": suffix,
    }
