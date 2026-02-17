import pytest
import uuid


@pytest.mark.asyncio
async def test_auth_login_success(http_session, base_url):
    """POST /api/v1/auth с валидными данными возвращает 200, token и user."""
    url = f"{base_url}/api/v1/auth"
    payload = {"email": "admin@test.com", "password": "admin123"}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "token" in data
        assert "user" in data
        user = data["user"]
        assert user.get("email") == "admin@test.com"
        assert "password" not in user
        assert user.get("role") == "admin"
        assert "id" in user
        assert "first_name" in user


@pytest.mark.asyncio
async def test_auth_login_invalid_password(http_session, base_url):
    """POST /api/v1/auth с неверным паролем возвращает 401."""
    url = f"{base_url}/api/v1/auth"
    payload = {"email": "admin@test.com", "password": "wrong"}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert "error" in data or data.get("code") == "UNAUTHORIZED" or resp.status == 401


@pytest.mark.asyncio
async def test_auth_login_invalid_email(http_session, base_url):
    """POST /api/v1/auth с несуществующим email возвращает 401."""
    url = f"{base_url}/api/v1/auth"
    payload = {"email": "nonexistent@test.com", "password": "any"}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401



@pytest.mark.asyncio
async def test_users_list_requires_auth(http_session, base_url):
    """GET /api/v1/users без токена возвращает 401."""
    url = f"{base_url}/api/v1/users"
    async with http_session.get(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_users_list_admin_success(http_session, base_url, auth_headers_admin):
    """GET /api/v1/users от admin возвращает 200 и массив users."""
    url = f"{base_url}/api/v1/users"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "users" in data
        assert isinstance(data["users"], list)
        for u in data["users"]:
            assert "password" not in u
            assert "id" in u
            assert "email" in u
            assert "role" in u


@pytest.mark.asyncio
async def test_users_list_filter_by_role(
    http_session, base_url, auth_headers_admin
):
    """GET /api/v1/users?role=experimenter возвращает 200."""
    url = f"{base_url}/api/v1/users?role=experimenter"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "users" in data
        for u in data["users"]:
            assert u.get("role") == "experimenter"


@pytest.mark.asyncio
async def test_users_list_forbidden_for_experimenter(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/users от experimenter возвращает 403."""
    url = f"{base_url}/api/v1/users"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN" or "permission" in data.get("message", "").lower() or resp.status == 403


@pytest.mark.asyncio
async def test_users_create_success(http_session, base_url, auth_headers_admin):
    """POST /api/v1/users создаёт пользователя, возвращает 201."""
    url = f"{base_url}/api/v1/users"
    unique = uuid.uuid4().hex[:8]
    payload = {
        "email": f"newuser_{unique}@test.com",
        "first_name": f"NewUser_{unique}",
        "password": "secret123",
        "role": "viewer",
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert "password" not in data
        assert data["email"] == payload["email"]
        assert data["first_name"] == payload["first_name"]
        assert data["role"] == "viewer"
        assert "id" in data
        assert "created_at" in data or "id" in data


@pytest.mark.asyncio
async def test_users_create_duplicate_email_returns_409(
    http_session, base_url, auth_headers_admin
):
    """POST /api/v1/users с существующим email возвращает 409."""
    url = f"{base_url}/api/v1/users"
    payload = {
        "email": "admin@test.com",
        "first_name": "AnotherName",
        "password": "pass",
        "role": "viewer",
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 409


@pytest.mark.asyncio
async def test_users_create_forbidden_for_experimenter(
    http_session, base_url, auth_headers_experimenter
):
    """POST /api/v1/users от experimenter возвращает 403."""
    url = f"{base_url}/api/v1/users"
    payload = {
        "email": "x@test.com",
        "first_name": "X",
        "password": "p",
        "role": "viewer",
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_users_get_by_id_admin(
    http_session, base_url, auth_headers_admin, auth_headers_experimenter
):
    """GET /api/v1/users/{id} — admin получает любого пользователя."""
    url_login = f"{base_url}/api/v1/auth"
    async with http_session.post(
        url_login, json={"email": "experimenter@test.com", "password": "exp123"}
    ) as r:
        assert r.status == 200
        user_id = (await r.json())["user"]["id"]

    url = f"{base_url}/api/v1/users/{user_id}"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == user_id
        assert data["email"] == "experimenter@test.com"
        assert "password" not in data


@pytest.mark.asyncio
async def test_users_get_own_profile(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/users/{id} — пользователь может получить свой профиль."""
    url_login = f"{base_url}/api/v1/auth"
    async with http_session.post(
        url_login, json={"email": "experimenter@test.com", "password": "exp123"}
    ) as r:
        assert r.status == 200
        user_id = (await r.json())["user"]["id"]

    url = f"{base_url}/api/v1/users/{user_id}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == user_id
        assert data["email"] == "experimenter@test.com"


@pytest.mark.asyncio
async def test_users_get_other_profile_forbidden(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/users/{id} — experimenter не может получить чужой профиль (admin)."""
    async with http_session.post(
        f"{base_url}/api/v1/auth",
        json={"email": "admin@test.com", "password": "admin123"},
    ) as r:
        assert r.status == 200
        admin_id = (await r.json())["user"]["id"]

    url = f"{base_url}/api/v1/users/{admin_id}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_users_get_not_found(http_session, base_url, auth_headers_admin):
    """GET /api/v1/users/{id} с несуществующим id возвращает 404."""
    url = f"{base_url}/api/v1/users/00000000-0000-0000-0000-000000000001"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND" or "not found" in data.get("message", "").lower()


@pytest.mark.asyncio
async def test_users_update_success(http_session, base_url, auth_headers_admin):
    """PATCH /api/v1/users/{id} обновляет пользователя (admin)."""
    unique = uuid.uuid4().hex[:8]
    create_url = f"{base_url}/api/v1/users"
    async with http_session.post(
        create_url,
        json={
            "email": f"patch_target_{unique}@test.com",
            "first_name": f"PatchTarget_{unique}",
            "password": "oldpass",
            "role": "viewer",
        },
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status == 201
        user_id = (await cr.json())["id"]

    patch_url = f"{base_url}/api/v1/users/{user_id}"
    async with http_session.patch(
        patch_url,
        json={"first_name": "UpdatedName", "role": "experimenter"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["first_name"] == "UpdatedName"
        assert data["role"] == "experimenter"
        assert data["id"] == user_id


@pytest.mark.asyncio
async def test_users_update_not_found(http_session, base_url, auth_headers_admin):
    """PATCH /api/v1/users/{id} для несуществующего id возвращает 404."""
    url = f"{base_url}/api/v1/users/00000000-0000-0000-0000-000000000001"
    async with http_session.patch(
        url,
        json={"first_name": "X"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_users_update_forbidden_for_experimenter(
    http_session, base_url, auth_headers_experimenter
):
    """PATCH /api/v1/users/{id} от experimenter (не admin) возвращает 403."""
    async with http_session.post(
        f"{base_url}/api/v1/auth",
        json={"email": "admin@test.com", "password": "admin123"},
    ) as r:
        admin_id = (await r.json())["user"]["id"]

    url = f"{base_url}/api/v1/users/{admin_id}"
    async with http_session.patch(
        url,
        json={"first_name": "Hack"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 403
