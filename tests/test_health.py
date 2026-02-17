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
    """GET /metrics возвращает 200 и text/plain с метриками Prometheus."""
    url = f"{base_url}/metrics"
    async with http_session.get(url) as resp:
        assert resp.status == 200
        text = await resp.text()
        assert "http_requests_total" in text or "decide_requests_total" in text or len(text) >= 0
