import pytest


@pytest.mark.asyncio
async def test_health(http_session, base_url):
    url = f"{base_url}/health"
    async with http_session.get(url) as resp:
        assert resp.status == 200


@pytest.mark.asyncio
async def test_ready(http_session, base_url):
    url = f"{base_url}/ready"
    async with http_session.get(url) as resp:
        assert resp.status in (200, 503)


@pytest.mark.asyncio
async def test_metrics_prometheus(http_session, base_url):
    url = f"{base_url}/metrics"
    async with http_session.get(url) as resp:
        assert resp.status == 200
        assert resp.content_type == "text/plain"
        text = await resp.text()
        assert "# TYPE " in text
        assert "http_requests_total" in text or "decide_requests_total" in text
