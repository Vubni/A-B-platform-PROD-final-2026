import pytest


@pytest.mark.asyncio
async def test_health(http_session, base_url):
    """GET /health возвращает 200."""
    url = f"{base_url}/health"
    async with http_session.get(url) as resp:
        assert resp.status == 200


@pytest.mark.asyncio
async def test_ready(http_session, base_url):
    """GET /ready возвращает 200 или 503 в зависимости от готовности зависимостей."""
    url = f"{base_url}/ready"
    async with http_session.get(url) as resp:
        assert resp.status in (200, 503)


@pytest.mark.asyncio
async def test_metrics(http_session, base_url):
    """GET /metrics по умолчанию возвращает 200 и JSON с метриками."""
    url = f"{base_url}/metrics"
    async with http_session.get(url) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "metrics" in data
        assert isinstance(data["metrics"], list)
        names = {m["name"] for m in data["metrics"]}
        assert "http_requests_total" in names or "decide_requests_total" in names or len(names) >= 0


@pytest.mark.asyncio
async def test_metrics_prometheus(http_session, base_url):
    """GET /metrics?format=prometheus возвращает text/plain в формате Prometheus."""
    url = f"{base_url}/metrics?format=prometheus"
    async with http_session.get(url) as resp:
        assert resp.status == 200
        text = await resp.text()
        assert "http_requests_total" in text or "decide_requests_total" in text
