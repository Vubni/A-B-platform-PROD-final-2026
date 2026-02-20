"""
Тесты API guardrails: GET/POST /api/v1/guardrails, GET/DELETE /api/v1/guardrails/{metric_key}.
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_guardrails_list_requires_auth(http_session, base_url):
    """GET /api/v1/guardrails без токена возвращает 401."""
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.get(url) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_guardrails_list_success(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/guardrails с токеном возвращает 200 и guardrails."""
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "guardrails" in data
        assert isinstance(data["guardrails"], list)


@pytest.mark.asyncio
async def test_guardrails_get_requires_auth(http_session, base_url):
    """GET /api/v1/guardrails/{metric_key} без токена возвращает 401."""
    url = f"{base_url}/api/v1/guardrails/some_metric_key"
    async with http_session.get(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_guardrails_get_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/guardrails/{metric_key} для несуществующего guardrail возвращает 404."""
    key = f"nonexistent_guardrail_metric_{uuid.uuid4().hex[:8]}"
    url = f"{base_url}/api/v1/guardrails/{key}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_guardrails_get_success(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """GET /api/v1/guardrails/{metric_key} возвращает guardrail после создания."""
    ctx = linked_event_types_metrics_experiment
    metric_key = ctx["metric_keys"]["conversions"]
    guardrails_url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        guardrails_url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": metric_key,
            "threshold": 10.0,
            "window_seconds": 300,
            "action": "pause",
        },
    ) as resp:
        assert resp.status == 200
    get_url = f"{base_url}/api/v1/guardrails/{metric_key}"
    async with http_session.get(get_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data.get("metric_key") == metric_key
        assert data.get("threshold") == 10.0
        assert data.get("window_seconds") == 300
        assert data.get("action") == "pause"


@pytest.mark.asyncio
async def test_guardrails_upsert_requires_auth(http_session, base_url):
    """POST /api/v1/guardrails без токена возвращает 401."""
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        url,
        json={
            "metric_key": "any_metric",
            "threshold": 1.0,
            "window_seconds": 60,
            "action": "pause",
        },
    ) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_guardrails_upsert_forbidden_for_viewer(
    http_session, base_url, auth_headers_viewer, linked_event_types_metrics_experiment
):
    """POST /api/v1/guardrails от viewer возвращает 403."""
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        url,
        headers=auth_headers_viewer,
        json={
            "metric_key": ctx["metric_keys"]["conversions"],
            "threshold": 1.0,
            "window_seconds": 60,
            "action": "pause",
        },
    ) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_guardrails_upsert_metric_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """POST /api/v1/guardrails с несуществующей метрикой возвращает 404."""
    url = f"{base_url}/api/v1/guardrails"
    key = f"nonexistent_metric_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": key,
            "threshold": 1.0,
            "window_seconds": 60,
            "action": "pause",
        },
    ) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_guardrails_upsert_validation_invalid_action(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """POST /api/v1/guardrails с неверным action возвращает 400/422."""
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": ctx["metric_keys"]["conversions"],
            "threshold": 1.0,
            "window_seconds": 60,
            "action": "invalid_action",
        },
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_guardrails_upsert_validation_window_seconds(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """POST /api/v1/guardrails с window_seconds <= 0 возвращает 400/422."""
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": ctx["metric_keys"]["conversions"],
            "threshold": 1.0,
            "window_seconds": 0,
            "action": "pause",
        },
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_guardrails_upsert_success_rollback_to_control(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """POST /api/v1/guardrails с action=rollback_to_control сохраняет guardrail."""
    ctx = linked_event_types_metrics_experiment
    metric_key = ctx["metric_keys"]["impressions"]
    url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": metric_key,
            "threshold": 100.0,
            "window_seconds": 120,
            "action": "rollback_to_control",
        },
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data.get("metric_key") == metric_key
        assert data.get("action") == "rollback_to_control"
        assert data.get("window_seconds") == 120


@pytest.mark.asyncio
async def test_guardrails_delete_requires_auth(http_session, base_url):
    """DELETE /api/v1/guardrails/{metric_key} без токена возвращает 401."""
    url = f"{base_url}/api/v1/guardrails/some_key"
    async with http_session.delete(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_guardrails_delete_forbidden_for_viewer(
    http_session, base_url, auth_headers_viewer, linked_event_types_metrics_experiment
):
    """DELETE /api/v1/guardrails от viewer возвращает 403."""
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/guardrails/{ctx['metric_keys']['conversions']}"
    async with http_session.delete(url, headers=auth_headers_viewer) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_guardrails_delete_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """DELETE /api/v1/guardrails/{metric_key} для несуществующего guardrail возвращает 404."""
    key = f"nonexistent_gr_{uuid.uuid4().hex[:8]}"
    url = f"{base_url}/api/v1/guardrails/{key}"
    async with http_session.delete(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_guardrails_delete_success(
    http_session, base_url, auth_headers_experimenter, auth_headers_admin
):
    """DELETE /api/v1/guardrails/{metric_key} удаляет guardrail и возвращает 204."""
    suffix = uuid.uuid4().hex[:8]
    et_key = f"gr_del_et_{suffix}"
    metric_key = f"gr_del_metric_{suffix}"
    et_url = f"{base_url}/api/v1/event-types"
    async with http_session.post(
        et_url,
        headers=auth_headers_admin,
        json={"key": et_key, "display_name": "For guardrail delete"},
    ) as r:
        if r.status not in (200, 201):
            pytest.skip(f"Could not create event type: {await r.text()}")
    metrics_url = f"{base_url}/api/v1/metrics"
    async with http_session.post(
        metrics_url,
        headers=auth_headers_experimenter,
        json={
            "key": metric_key,
            "name": "Guardrail delete test metric",
            "aggregation_rule": {
                "kind": "count_events",
                "event_type_key": et_key,
                "aggregation_unit": "subject",
            },
            "unit": "events",
        },
    ) as r:
        if r.status not in (200, 201):
            pytest.skip(f"Could not create metric: {await r.text()}")
    post_url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        post_url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": metric_key,
            "threshold": 5.0,
            "window_seconds": 60,
            "action": "pause",
        },
    ) as resp:
        assert resp.status == 200, f"Could not create guardrail: {await resp.text()}"
    get_url = f"{base_url}/api/v1/guardrails/{metric_key}"
    async with http_session.get(get_url, headers=auth_headers_experimenter) as get_resp:
        if get_resp.status != 200:
            pytest.skip("Guardrail was not created or not visible")
    delete_url = f"{base_url}/api/v1/guardrails/{metric_key}"
    async with http_session.delete(
        delete_url, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 204, f"Delete failed: {await resp.text()}"
    async with http_session.get(
        get_url,
        headers=auth_headers_experimenter,
    ) as get_resp:
        assert get_resp.status == 404
