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
    "test_approver_groups_api.py": "Approver groups",
    "test_flags_api.py": "Flags",
    "test_experiments_api.py": "Experiments",
    "test_experiment_validation.py": "Experiments (validation)",
    "test_guardrails_api.py": "Guardrails",
    "test_decide_api.py": "Decide",
    "test_events_api.py": "Events",
    "test_reports_api.py": "Reports",
    "test_metrics_catalog_api.py": "Metrics catalog",
    "test_conflicts_api.py": "Conflict resolution",
    "test_autopilot_ramp_api.py": "Autopilot ramp-up",
    "test_learnings_api.py": "Learnings library",
}

CORE_SECTION_ORDER = [
    "Health",
    "Users",
    "Approver groups",
    "Flags",
    "Experiments",
    "Experiments (validation)",
    "Guardrails",
    "Decide",
    "Events",
    "Reports",
    "Metrics catalog",
]

EXTRA_SECTION_ORDER = [
    "Conflict resolution",
    "Autopilot ramp-up",
    "Learnings library",
]

SECTION_ORDER = CORE_SECTION_ORDER + EXTRA_SECTION_ORDER

SECTION_GROUPS = {
    **dict.fromkeys(CORE_SECTION_ORDER, "CORE FUNCTIONALITY"),
    **dict.fromkeys(EXTRA_SECTION_ORDER, "EXTRA FEATURES"),
}

ALL_ENDPOINTS = [
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/metrics"),
    ("POST", "/api/v1/auth"),
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("GET", "/api/v1/users/{id}"),
    ("PATCH", "/api/v1/users/{id}"),
    ("GET", "/api/v1/approver-groups"),
    ("POST", "/api/v1/approver-groups"),
    ("PATCH", "/api/v1/approver-groups/{id}"),
    ("POST", "/api/v1/flags"),
    ("GET", "/api/v1/flags"),
    ("GET", "/api/v1/flags/{key}"),
    ("PATCH", "/api/v1/flags/{key}"),
    ("POST", "/api/v1/experiments"),
    ("GET", "/api/v1/experiments"),
    ("GET", "/api/v1/experiments/{id}"),
    ("PATCH", "/api/v1/experiments/{id}"),
    ("PATCH", "/api/v1/experiments/{id}/status"),
    ("POST", "/api/v1/experiments/{id}/complete"),
    ("POST", "/api/v1/experiments/{id}/variants"),
    ("PATCH", "/api/v1/experiments/{id}/variants/{variant_id}"),
    ("DELETE", "/api/v1/experiments/{id}/variants/{variant_id}"),
    ("GET", "/api/v1/experiments/{id}/guardrail-history"),
    ("GET", "/api/v1/experiments/{id}/ramp-plan"),
    ("PUT", "/api/v1/experiments/{id}/ramp-plan"),
    ("DELETE", "/api/v1/experiments/{id}/ramp-plan"),
    ("GET", "/api/v1/experiments/{id}/ramp-state"),
    ("POST", "/api/v1/experiments/{id}/ramp-start"),
    ("PATCH", "/api/v1/experiments/{id}/ramp-mode"),
    ("POST", "/api/v1/experiments/{id}/ramp-override"),
    ("GET", "/api/v1/experiments/{id}/ramp-decision-log"),
    ("GET", "/api/v1/guardrails"),
    ("GET", "/api/v1/guardrails/{metric_key}"),
    ("POST", "/api/v1/guardrails"),
    ("DELETE", "/api/v1/guardrails/{metric_key}"),
    ("GET", "/api/v1/conflict-domains"),
    ("POST", "/api/v1/conflict-domains"),
    ("GET", "/api/v1/conflict-domains/{id}"),
    ("PATCH", "/api/v1/conflict-domains/{id}"),
    ("DELETE", "/api/v1/conflict-domains/{id}"),
    ("GET", "/api/v1/experiments/{id}/conflict-bindings"),
    ("POST", "/api/v1/experiments/{id}/conflict-bindings"),
    ("DELETE", "/api/v1/experiments/{id}/conflict-bindings/{domain_id}"),
    ("GET", "/api/v1/experiments/{id}/conflict-preflight"),
    ("GET", "/api/v1/experiments/{id}/conflict-log"),
    ("POST", "/api/v1/decide"),
    ("POST", "/api/v1/events"),
    ("GET", "/api/v1/event-types"),
    ("POST", "/api/v1/event-types"),
    ("GET", "/api/v1/event-types/{id}"),
    ("PATCH", "/api/v1/event-types/{id}"),
    ("DELETE", "/api/v1/event-types/{id}"),
    ("GET", "/api/v1/experiments/{id}/report"),
    ("GET", "/api/v1/learnings"),
    ("GET", "/api/v1/learnings/{id}"),
    ("GET", "/api/v1/learnings/{id}/audit"),
    ("GET", "/api/v1/learnings/{id}/similar"),
    ("GET", "/api/v1/experiments/{id}/learning"),
    ("PUT", "/api/v1/experiments/{id}/learning"),
    ("GET", "/api/v1/metrics"),
    ("GET", "/api/v1/metrics/{key}"),
    ("POST", "/api/v1/metrics"),
    ("PATCH", "/api/v1/metrics/{key}"),
]

TESTED_ENDPOINTS = [
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/metrics"),
    ("POST", "/api/v1/auth"),
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("GET", "/api/v1/users/{id}"),
    ("PATCH", "/api/v1/users/{id}"),
    ("GET", "/api/v1/approver-groups"),
    ("POST", "/api/v1/approver-groups"),
    ("PATCH", "/api/v1/approver-groups/{id}"),
    ("POST", "/api/v1/flags"),
    ("GET", "/api/v1/flags"),
    ("GET", "/api/v1/flags/{key}"),
    ("PATCH", "/api/v1/flags/{key}"),
    ("POST", "/api/v1/experiments"),
    ("GET", "/api/v1/experiments"),
    ("GET", "/api/v1/experiments/{id}"),
    ("PATCH", "/api/v1/experiments/{id}"),
    ("PATCH", "/api/v1/experiments/{id}/status"),
    ("POST", "/api/v1/experiments/{id}/complete"),
    ("POST", "/api/v1/experiments/{id}/variants"),
    ("PATCH", "/api/v1/experiments/{id}/variants/{variant_id}"),
    ("DELETE", "/api/v1/experiments/{id}/variants/{variant_id}"),
    ("GET", "/api/v1/experiments/{id}/guardrail-history"),
    ("GET", "/api/v1/experiments/{id}/ramp-plan"),
    ("PUT", "/api/v1/experiments/{id}/ramp-plan"),
    ("DELETE", "/api/v1/experiments/{id}/ramp-plan"),
    ("GET", "/api/v1/experiments/{id}/ramp-state"),
    ("POST", "/api/v1/experiments/{id}/ramp-start"),
    ("PATCH", "/api/v1/experiments/{id}/ramp-mode"),
    ("POST", "/api/v1/experiments/{id}/ramp-override"),
    ("GET", "/api/v1/experiments/{id}/ramp-decision-log"),
    ("GET", "/api/v1/guardrails"),
    ("GET", "/api/v1/guardrails/{metric_key}"),
    ("POST", "/api/v1/guardrails"),
    ("DELETE", "/api/v1/guardrails/{metric_key}"),
    ("GET", "/api/v1/conflict-domains"),
    ("POST", "/api/v1/conflict-domains"),
    ("GET", "/api/v1/conflict-domains/{id}"),
    ("PATCH", "/api/v1/conflict-domains/{id}"),
    ("DELETE", "/api/v1/conflict-domains/{id}"),
    ("GET", "/api/v1/experiments/{id}/conflict-bindings"),
    ("POST", "/api/v1/experiments/{id}/conflict-bindings"),
    ("DELETE", "/api/v1/experiments/{id}/conflict-bindings/{domain_id}"),
    ("GET", "/api/v1/experiments/{id}/conflict-preflight"),
    ("GET", "/api/v1/experiments/{id}/conflict-log"),
    ("POST", "/api/v1/decide"),
    ("POST", "/api/v1/events"),
    ("GET", "/api/v1/event-types"),
    ("POST", "/api/v1/event-types"),
    ("GET", "/api/v1/event-types/{id}"),
    ("PATCH", "/api/v1/event-types/{id}"),
    ("DELETE", "/api/v1/event-types/{id}"),
    ("GET", "/api/v1/experiments/{id}/report"),
    ("GET", "/api/v1/learnings"),
    ("GET", "/api/v1/learnings/{id}"),
    ("GET", "/api/v1/learnings/{id}/audit"),
    ("GET", "/api/v1/learnings/{id}/similar"),
    ("GET", "/api/v1/experiments/{id}/learning"),
    ("PUT", "/api/v1/experiments/{id}/learning"),
    ("GET", "/api/v1/metrics"),
    ("GET", "/api/v1/metrics/{key}"),
    ("POST", "/api/v1/metrics"),
    ("PATCH", "/api/v1/metrics/{key}"),
]


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
    section_rank = {section: idx for idx, section in enumerate(SECTION_ORDER)}
    items.sort(
        key=lambda item: (
            section_rank.get(_section_for_nodeid(item.nodeid), 10_000),
            item.nodeid,
        )
    )


def pytest_report_collectionfinish(config, start_path, items):
    groups = {}
    for item in items:
        section = _section_for_nodeid(item.nodeid)
        groups.setdefault(section, []).append(item.nodeid.split("::")[-1])
    order = SECTION_ORDER + [s for s in sorted(groups) if s not in SECTION_ORDER]
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


def pytest_sessionfinish(session, exitstatus):
    """Вывод отчёта покрытия эндпоинтов (не покрытия кода)."""
    all_set = set(ALL_ENDPOINTS)
    tested_set = set(TESTED_ENDPOINTS)
    covered = all_set & tested_set
    total = len(all_set)
    num_covered = len(covered)
    pct = (100.0 * num_covered / total) if total else 0
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    reporter.ensure_newline()
    reporter.write_line("")
    reporter.write_line("=== Покрытие эндпоинтов ===")
    reporter.write_line("")
    reporter.write_line("Протестированные эндпоинты:")
    for method, path in sorted(covered, key=lambda x: (x[1], x[0])):
        reporter.write_line(f"  {method:6} {path}")
    reporter.write_line("")
    uncovered = all_set - tested_set
    if uncovered:
        reporter.write_line("Непротестированные эндпоинты:")
        for method, path in sorted(uncovered, key=lambda x: (x[1], x[0])):
            reporter.write_line(f"  {method:6} {path}")
        reporter.write_line("")
    reporter.write_line(f"Итого: {num_covered}/{total} эндпоинтов — {pct:.0f}%")
    reporter.write_line("")


_last_section = [None]
_last_group = [None]


def pytest_runtest_setup(item):
    section = _section_for_nodeid(item.nodeid)
    group = SECTION_GROUPS.get(section, "OTHER")
    if _last_group[0] != group:
        _last_group[0] = group
        reporter = item.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.ensure_newline()
            reporter.write_line(f"=== {group} ===")
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


async def transition_experiment_to_running(
    http_session,
    base_url,
    exp_id,
    auth_headers_experimenter,
    auth_headers_approver,
) -> bool:
    """Переводит эксперимент on_review -> approved -> running. Возвращает True при успехе, False при 409."""
    for status, role in [
        ("on_review", auth_headers_experimenter),
        ("approved", auth_headers_approver),
        ("running", auth_headers_experimenter),
    ]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=role,
            json={"status": status},
        ) as r:
            if r.status == 409 and status == "running":
                return False
            if r.status != 200:
                text = await r.text()
                raise RuntimeError(f"Could not set status {status}: {text}")
    return True


async def create_experiment_in_running(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_admin,
    key_prefix: str = "complete",
) -> str:
    """Создаёт флаг, эксперимент с двумя вариантами и переводит в running. При 409 повторяет с новым флагом. Возвращает exp_id."""
    flags_url = f"{base_url}/api/v1/flags"
    create_url = f"{base_url}/api/v1/experiments"
    for _attempt in range(2):
        key = f"{key_prefix}_{uuid.uuid4().hex[:12]}"
        async with http_session.post(
            flags_url,
            headers=auth_headers_admin,
            json={"key": key, "value_type": "string", "default_value": "c"},
        ) as fr:
            if fr.status != 201:
                raise RuntimeError(f"Could not create flag: {(await fr.text())}")
            flag_id = (await fr.json())["id"]
        async with http_session.post(
            create_url,
            json={"flag_id": flag_id, "name": f"Complete test {key}", "audience_fraction": 0.5},
            headers=auth_headers_experimenter,
        ) as cr:
            if cr.status != 201:
                raise RuntimeError(f"Could not create experiment: {(await cr.text())}")
            exp_id = (await cr.json())["id"]
        var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
        for v in [
            {"variant_name": "control", "variant_value": "c", "weight": 0.25, "is_control": True},
            {"variant_name": "treatment", "variant_value": "t", "weight": 0.25, "is_control": False},
        ]:
            async with http_session.post(var_url, headers=auth_headers_experimenter, json=v) as vr:
                assert vr.status == 201, f"Variant add failed: {(await vr.text())}"
        ok = await transition_experiment_to_running(
            http_session, base_url, exp_id, auth_headers_experimenter, auth_headers_approver
        )
        if ok:
            return exp_id
    raise AssertionError("Could not set status running (retry with new flag)")


@pytest.fixture
async def linked_event_types_metrics_experiment(
    http_session,
    base_url,
    auth_headers_admin,
    auth_headers_experimenter,
):
    return await _create_linked_event_types_metrics_experiment(
        http_session, base_url, auth_headers_admin, auth_headers_experimenter
    )


async def _create_linked_event_types_metrics_experiment(
    http_session, base_url, auth_headers_admin, auth_headers_experimenter
):
    """Создаёт связанные event types, метрики, флаг и эксперимент с вариантами (draft). Возвращает контекст-словарь."""
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


@pytest.fixture
async def linked_event_types_metrics_experiment_running(
    http_session,
    base_url,
    auth_headers_admin,
    auth_headers_experimenter,
    auth_headers_approver,
):
    """linked_event_types_metrics_experiment + on_review -> approved -> running с одной повторной попыткой при 409."""
    ctx = await _create_linked_event_types_metrics_experiment(
        http_session, base_url, auth_headers_admin, auth_headers_experimenter
    )
    if await transition_experiment_to_running(
        http_session, base_url, ctx["experiment_id"], auth_headers_experimenter, auth_headers_approver
    ):
        return ctx
    ctx2 = await _create_linked_event_types_metrics_experiment(
        http_session, base_url, auth_headers_admin, auth_headers_experimenter
    )
    if await transition_experiment_to_running(
        http_session, base_url, ctx2["experiment_id"], auth_headers_experimenter, auth_headers_approver
    ):
        return ctx2
    pytest.skip("Could not set status running for linked experiment (retry)")
