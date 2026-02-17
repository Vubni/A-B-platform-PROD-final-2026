import pytest


@pytest.mark.asyncio
async def test_flags_list_requires_auth(http_session, base_url):
    """GET /api/v1/flags без токена возвращает 401."""
    url = f"{base_url}/api/v1/flags"
    async with http_session.get(url) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_flags_list_success(http_session, base_url, auth_headers_admin):
    """GET /api/v1/flags с токеном возвращает 200 и массив flags."""
    url = f"{base_url}/api/v1/flags"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)


@pytest.mark.asyncio
async def test_flags_get_requires_auth(http_session, base_url):
    """GET /api/v1/flags/{key} без токена возвращает 401."""
    url = f"{base_url}/api/v1/flags/some_key"
    async with http_session.get(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_flags_get_success(http_session, base_url, auth_headers_admin):
    """GET /api/v1/flags/test_feature_flag возвращает флаг (после seed)."""
    url = f"{base_url}/api/v1/flags/test_feature_flag"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["key"] == "test_feature_flag"
        assert "id" in data
        assert data["default_value"] == "control"
        assert data["value_type"] == "string"


@pytest.mark.asyncio
async def test_flags_get_not_found(http_session, base_url, auth_headers_admin):
    """GET /api/v1/flags/{key} с несуществующим ключом возвращает 404."""
    url = f"{base_url}/api/v1/flags/nonexistent_flag_xyz_123"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_flags_create_requires_auth(http_session, base_url):
    """POST /api/v1/flags без токена возвращает 401."""
    url = f"{base_url}/api/v1/flags"
    payload = {
        "key": "auth_test_flag",
        "value_type": "string",
        "default_value": "off",
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_flags_create_success(http_session, base_url, auth_headers_admin):
    """POST /api/v1/flags создаёт флаг, возвращает 201."""
    url = f"{base_url}/api/v1/flags"
    key = "api_test_flag_string"
    payload = {
        "key": key,
        "value_type": "string",
        "default_value": "initial",
        "description": "Created by flags API test",
    }
    async with http_session.post(url, json=payload, headers=auth_headers_admin) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["key"] == key
        assert data["value_type"] == "string"
        assert data["default_value"] == "initial"
        assert "id" in data
        assert data.get("description") == "Created by flags API test"


@pytest.mark.asyncio
async def test_flags_create_number_and_bool(
    http_session, base_url, auth_headers_admin
):
    """POST /api/v1/flags с value_type number и bool."""
    url = f"{base_url}/api/v1/flags"
    async with http_session.post(
        url,
        json={"key": "api_test_flag_number", "value_type": "number", "default_value": "42"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["value_type"] == "number"
        assert data["default_value"] == "42"
    async with http_session.post(
        url,
        json={"key": "api_test_flag_bool", "value_type": "bool", "default_value": "true"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["value_type"] == "bool"
        assert data["default_value"].lower() in ("true", "1", "yes")


@pytest.mark.asyncio
async def test_flags_create_duplicate_key_returns_409(
    http_session, base_url, auth_headers_admin
):
    """POST /api/v1/flags с ключом, который уже есть, возвращает 409."""
    url = f"{base_url}/api/v1/flags"
    payload = {
        "key": "test_feature_flag",
        "value_type": "string",
        "default_value": "other",
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 409
        data = await resp.json()
        assert data.get("code") == "KEY_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_flags_create_invalid_key_returns_400(
    http_session, base_url, auth_headers_admin
):
    """POST /api/v1/flags с ключом, начинающимся с цифры, возвращает 400."""
    url = f"{base_url}/api/v1/flags"
    payload = {
        "key": "123invalid",
        "value_type": "string",
        "default_value": "x",
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_flags_update_success(http_session, base_url, auth_headers_admin):
    """PATCH /api/v1/flags/{key} обновляет default_value."""
    create_url = f"{base_url}/api/v1/flags"
    key = "api_test_flag_to_patch"
    async with http_session.post(
        create_url,
        json={"key": key, "value_type": "string", "default_value": "old"},
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status == 201

    patch_url = f"{base_url}/api/v1/flags/{key}"
    async with http_session.patch(
        patch_url,
        json={"default_value": "new_value"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["default_value"] == "new_value"
        assert data["key"] == key


@pytest.mark.asyncio
async def test_flags_update_not_found(http_session, base_url, auth_headers_admin):
    """PATCH /api/v1/flags/{key} для несуществующего флага возвращает 404."""
    url = f"{base_url}/api/v1/flags/nonexistent_patch_xyz"
    async with http_session.patch(
        url,
        json={"default_value": "x"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_flags_create_as_experimenter(http_session, base_url, auth_headers_experimenter):
    """Experimenter может создавать флаги (роль admin или experimenter)."""
    url = f"{base_url}/api/v1/flags"
    key = "api_test_flag_by_experimenter"
    async with http_session.post(
        url,
        json={"key": key, "value_type": "string", "default_value": "v"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["key"] == key
