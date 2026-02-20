"""
Тесты API каталога метрик: GET/POST /api/v1/metrics, GET/PATCH /api/v1/metrics/{key}.
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_metrics_list_requires_auth(http_session, base_url):
    """GET /api/v1/metrics без токена возвращает 401."""
    url = f"{base_url}/api/v1/metrics"
    async with http_session.get(url) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_metrics_list_success(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/metrics с токеном (experimenter/viewer/approver) возвращает 200 и metrics."""
    url = f"{base_url}/api/v1/metrics"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "metrics" in data
        assert isinstance(data["metrics"], list)


@pytest.mark.asyncio
async def test_metrics_list_as_viewer(
    http_session, base_url, auth_headers_viewer
):
    """GET /api/v1/metrics от viewer возвращает 200."""
    url = f"{base_url}/api/v1/metrics"
    async with http_session.get(url, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "metrics" in data


@pytest.mark.asyncio
async def test_metrics_get_requires_auth(http_session, base_url):
    """GET /api/v1/metrics/{key} без токена возвращает 401."""
    url = f"{base_url}/api/v1/metrics/some_key"
    async with http_session.get(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_metrics_get_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/metrics/{key} для несуществующей метрики возвращает 404."""
    key = f"nonexistent_metric_{uuid.uuid4().hex[:8]}"
    url = f"{base_url}/api/v1/metrics/{key}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_metrics_get_success(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """GET /api/v1/metrics/{key} возвращает метрику из каталога."""
    ctx = linked_event_types_metrics_experiment
    key = ctx["metric_keys"]["impressions"]
    url = f"{base_url}/api/v1/metrics/{key}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data.get("key") == key
        assert "name" in data
        assert "aggregation_rule" in data
        assert "id" in data


@pytest.mark.asyncio
async def test_metrics_create_requires_auth(http_session, base_url):
    """POST /api/v1/metrics без токена возвращает 401."""
    url = f"{base_url}/api/v1/metrics"
    async with http_session.post(
        url,
        json={
            "key": f"metric_catalog_unauth_{uuid.uuid4().hex[:8]}",
            "name": "Unauth metric",
            "aggregation_rule": {
                "kind": "count_events",
                "event_type_key": "exposure",
                "aggregation_unit": "subject",
            },
        },
    ) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_metrics_create_forbidden_for_viewer(
    http_session, base_url, auth_headers_viewer, auth_headers_admin
):
    """POST /api/v1/metrics от viewer возвращает 403."""
    et_url = f"{base_url}/api/v1/event-types"
    key_et = f"metric_catalog_et_v_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url, headers=auth_headers_admin, json={"key": key_et, "display_name": "ET"}
    ) as _:
        pass
    url = f"{base_url}/api/v1/metrics"
    key = f"metric_catalog_viewer_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        url,
        headers=auth_headers_viewer,
        json={
            "key": key,
            "name": "Viewer metric",
            "aggregation_rule": {
                "kind": "count_events",
                "event_type_key": key_et,
                "aggregation_unit": "subject",
            },
        },
    ) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_metrics_create_success(
    http_session, base_url, auth_headers_experimenter, auth_headers_admin
):
    """POST /api/v1/metrics от experimenter создаёт метрику, возвращает 201."""
    et_url = f"{base_url}/api/v1/event-types"
    key_et = f"metric_catalog_et_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url,
        headers=auth_headers_admin,
        json={"key": key_et, "display_name": "For metric"},
    ) as r:
        if r.status not in (200, 201):
            pytest.skip("Could not create event type")
    url = f"{base_url}/api/v1/metrics"
    key = f"metric_catalog_new_{uuid.uuid4().hex[:8]}"
    payload = {
        "key": key,
        "name": "New catalog metric",
        "description": "Created by metrics catalog test",
        "aggregation_rule": {
            "kind": "count_events",
            "event_type_key": key_et,
            "aggregation_unit": "subject",
        },
        "attribution_rule": {"requires_decision": True},
        "unit": "events",
    }
    async with http_session.post(
        url, headers=auth_headers_experimenter, json=payload
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["key"] == key
        assert data["name"] == "New catalog metric"
        assert data.get("description") == "Created by metrics catalog test"
        assert "id" in data
        assert data.get("aggregation_rule", {}).get("kind") == "count_events"


@pytest.mark.asyncio
async def test_metrics_create_duplicate_key_returns_409(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """POST /api/v1/metrics с ключом, который уже есть, возвращает 409."""
    ctx = linked_event_types_metrics_experiment
    existing_key = ctx["metric_keys"]["impressions"]
    url = f"{base_url}/api/v1/metrics"
    async with http_session.get(
        f"{base_url}/api/v1/metrics/{existing_key}",
        headers=auth_headers_experimenter,
    ) as r:
        if r.status != 200:
            pytest.skip("Need existing metric")
        metric = await r.json()
    payload = {
        "key": existing_key,
        "name": metric.get("name", "Duplicate"),
        "aggregation_rule": metric.get("aggregation_rule", {}),
    }
    async with http_session.post(
        url, headers=auth_headers_experimenter, json=payload
    ) as resp:
        assert resp.status == 409
        data = await resp.json()
        assert data.get("code") == "KEY_ALREADY_EXISTS" or "key" in (data.get("message") or "").lower()


@pytest.mark.asyncio
async def test_metrics_update_requires_auth(http_session, base_url):
    """PATCH /api/v1/metrics/{key} без токена возвращает 401."""
    url = f"{base_url}/api/v1/metrics/some_key"
    async with http_session.patch(url, json={"name": "Updated"}) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_metrics_update_forbidden_for_experimenter(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """PATCH /api/v1/metrics/{key} от experimenter возвращает 403 (только admin)."""
    ctx = linked_event_types_metrics_experiment
    key = ctx["metric_keys"]["impressions"]
    url = f"{base_url}/api/v1/metrics/{key}"
    async with http_session.patch(
        url,
        headers=auth_headers_experimenter,
        json={"name": "Hacked name"},
    ) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_metrics_update_success(
    http_session, base_url, auth_headers_admin, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """PATCH /api/v1/metrics/{key} от admin обновляет метрику."""
    ctx = linked_event_types_metrics_experiment
    key = ctx["metric_keys"]["impressions"]
    url = f"{base_url}/api/v1/metrics/{key}"
    new_name = f"Updated impressions {uuid.uuid4().hex[:6]}"
    async with http_session.patch(
        url,
        headers=auth_headers_admin,
        json={"name": new_name},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["name"] == new_name
        assert data["key"] == key


@pytest.mark.asyncio
async def test_metrics_update_not_found(
    http_session, base_url, auth_headers_admin
):
    """PATCH /api/v1/metrics/{key} для несуществующей метрики возвращает 404."""
    key = f"nonexistent_metric_patch_{uuid.uuid4().hex[:8]}"
    url = f"{base_url}/api/v1/metrics/{key}"
    async with http_session.patch(
        url,
        headers=auth_headers_admin,
        json={"name": "Updated"},
    ) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"
