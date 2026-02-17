import os
import pytest
from aiohttp import ClientSession

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:80")


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
    """Токен пользователя admin@test.com (после seed_test_data.py)."""
    token, _ = await _login(http_session, base_url, "admin@test.com", "admin123")
    return token


@pytest.fixture
async def experimenter_token(http_session, base_url):
    """Токен пользователя experimenter@test.com."""
    token, _ = await _login(http_session, base_url, "experimenter@test.com", "exp123")
    return token


@pytest.fixture
async def auth_headers_experimenter(experimenter_token):
    return {"Authorization": f"Bearer {experimenter_token}"}


@pytest.fixture
async def auth_headers_admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
async def flag_id(http_session, base_url, auth_headers_admin):
    """ID флага test_feature_flag (должен быть создан seed-скриптом)."""
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
