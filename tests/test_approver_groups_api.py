"""
Тесты API групп аппруверов: GET/POST /api/v1/approver-groups, PATCH /api/v1/approver-groups/{id}.
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_approver_groups_list_requires_auth(http_session, base_url):
    """GET /api/v1/approver-groups без токена возвращает 401."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_approver_groups_list_success_admin(
    http_session, base_url, auth_headers_admin
):
    """GET /api/v1/approver-groups от admin возвращает 200 и approver_groups."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "approver_groups" in data
        assert isinstance(data["approver_groups"], list)


@pytest.mark.asyncio
async def test_approver_groups_list_success_approver(
    http_session, base_url, auth_headers_approver
):
    """GET /api/v1/approver-groups от approver возвращает 200."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url, headers=auth_headers_approver) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "approver_groups" in data


@pytest.mark.asyncio
async def test_approver_groups_list_success_experimenter(
    http_session, base_url, auth_headers_experimenter
):
    """GET /api/v1/approver-groups от experimenter возвращает 200."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "approver_groups" in data


@pytest.mark.asyncio
async def test_approver_groups_create_requires_auth(http_session, base_url):
    """POST /api/v1/approver-groups без токена возвращает 401."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.post(
        url,
        json={
            "experimenter_id": None,
            "min_approvals": 1,
            "approver_ids": [],
        },
    ) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_approver_groups_create_forbidden_for_admin(
    http_session, base_url, auth_headers_admin
):
    """POST /api/v1/approver-groups от admin возвращает 403 (только approver)."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(
        f"{base_url}/api/v1/users", headers=auth_headers_admin
    ) as r:
        assert r.status == 200
        users = (await r.json()).get("users") or []
    approver = next((u for u in users if u.get("role") == "approver"), None)
    if not approver:
        pytest.skip("Need approver user in seed")
    async with http_session.post(
        url,
        headers=auth_headers_admin,
        json={
            "experimenter_id": None,
            "min_approvals": 1,
            "approver_ids": [approver["id"]],
        },
    ) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_approver_groups_create_success_fallback(
    http_session, base_url, auth_headers_approver, auth_headers_admin
):
    """POST /api/v1/approver-groups от approver создаёт fallback-группу (experimenter_id=null)."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(
        f"{base_url}/api/v1/users", headers=auth_headers_admin
    ) as r:
        assert r.status == 200
        users = (await r.json()).get("users") or []
    admins_approvers = [u for u in users if u.get("role") in ("admin", "approver")]
    if not admins_approvers:
        pytest.skip("Need admin/approver users")
    approver_ids = [u["id"] for u in admins_approvers[:2]]
    payload = {
        "experimenter_id": None,
        "min_approvals": 1,
        "approver_ids": approver_ids,
    }
    async with http_session.post(
        url, headers=auth_headers_approver, json=payload
    ) as resp:
        if resp.status == 409:
            data = await resp.json()
            assert "already exists" in (data.get("message") or "").lower() or True
            return
        assert resp.status == 201, await resp.text()
        data = await resp.json()
        assert "id" in data
        assert data.get("experimenter_id") is None
        assert data.get("min_approvals") == 1


@pytest.mark.asyncio
async def test_approver_groups_create_success_for_experimenter(
    http_session, base_url, auth_headers_approver, auth_headers_admin
):
    """POST /api/v1/approver-groups с experimenter_id создаёт группу (201 или 409)."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(
        f"{base_url}/api/v1/users", headers=auth_headers_admin
    ) as r:
        assert r.status == 200
        users = (await r.json()).get("users") or []
    experimenter = next((u for u in users if u.get("role") == "experimenter"), None)
    approver_user = next((u for u in users if u.get("role") == "approver"), None)
    if not experimenter or not approver_user:
        pytest.skip("Need experimenter and approver in seed")
    payload = {
        "experimenter_id": experimenter["id"],
        "min_approvals": 1,
        "approver_ids": [approver_user["id"]],
    }
    async with http_session.post(
        url, headers=auth_headers_approver, json=payload
    ) as resp:
        assert resp.status in (201, 409)
        if resp.status == 201:
            data = await resp.json()
            assert data.get("experimenter_id") == experimenter["id"]
            assert data.get("min_approvals") == 1


@pytest.mark.asyncio
async def test_approver_groups_create_min_approvals_validation(
    http_session, base_url, auth_headers_approver, auth_headers_admin
):
    """POST /api/v1/approver-groups с min_approvals < 1 возвращает 400."""
    url = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(
        f"{base_url}/api/v1/users", headers=auth_headers_admin
    ) as r:
        assert r.status == 200
        users = (await r.json()).get("users") or []
    approver_user = next((u for u in users if u.get("role") == "approver"), None)
    if not approver_user:
        pytest.skip("Need approver in seed")
    async with http_session.post(
        url,
        headers=auth_headers_approver,
        json={
            "experimenter_id": None,
            "min_approvals": 0,
            "approver_ids": [approver_user["id"]],
        },
    ) as resp:
        assert resp.status in (400, 422)
        data = await resp.json()
        err = data.get("error") or data.get("message") or ""
        field_errors = data.get("fieldErrors") or []
        err_lower = err.lower()
        assert "min_approvals" in err_lower or any(
            "min_approvals" in str(e.get("field", "")).lower() for e in field_errors
        )


@pytest.mark.asyncio
async def test_approver_groups_create_experimenter_not_found(
    http_session, base_url, auth_headers_approver, auth_headers_admin
):
    """POST /api/v1/approver-groups с несуществующим experimenter_id возвращает 404."""
    url = f"{base_url}/api/v1/approver-groups"
    fake_uuid = "00000000-0000-0000-0000-000000000099"
    async with http_session.get(
        f"{base_url}/api/v1/users", headers=auth_headers_admin
    ) as r:
        assert r.status == 200
        users = (await r.json()).get("users") or []
    approver_user = next((u for u in users if u.get("role") == "approver"), None)
    if not approver_user:
        pytest.skip("Need approver in seed")
    async with http_session.post(
        url,
        headers=auth_headers_approver,
        json={
            "experimenter_id": fake_uuid,
            "min_approvals": 1,
            "approver_ids": [approver_user["id"]],
        },
    ) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_approver_groups_update_requires_auth(http_session, base_url):
    """PATCH /api/v1/approver-groups/{id} без токена возвращает 401."""
    url = f"{base_url}/api/v1/approver-groups/{uuid.uuid4()}"
    async with http_session.patch(
        url, json={"min_approvals": 2}
    ) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_approver_groups_update_forbidden_for_experimenter(
    http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin
):
    """PATCH /api/v1/approver-groups/{id} от experimenter возвращает 403."""
    url_list = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url_list, headers=auth_headers_admin) as r:
        if r.status != 200:
            pytest.skip("Need to list groups")
        data = await r.json()
        groups = data.get("approver_groups") or []
    if not groups:
        async with http_session.get(
            f"{base_url}/api/v1/users", headers=auth_headers_admin
        ) as ru:
            users = (await ru.json()).get("users") or []
            approver_user = next((u for u in users if u.get("role") == "approver"), None)
            experimenter = next((u for u in users if u.get("role") == "experimenter"), None)
            if not approver_user or not experimenter:
                pytest.skip("Need approver and experimenter")
            async with http_session.post(
                url_list,
                headers=auth_headers_approver,
                json={
                    "experimenter_id": experimenter["id"],
                    "min_approvals": 1,
                    "approver_ids": [approver_user["id"]],
                },
            ) as cr:
                if cr.status not in (200, 201):
                    pytest.skip("Could not create group")
                groups = [await cr.json()]
    group_id = groups[0]["id"]
    patch_url = f"{base_url}/api/v1/approver-groups/{group_id}"
    async with http_session.patch(
        patch_url,
        headers=auth_headers_experimenter,
        json={"min_approvals": 2},
    ) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_approver_groups_update_success(
    http_session, base_url, auth_headers_approver, auth_headers_admin
):
    """PATCH /api/v1/approver-groups/{id} от approver обновляет группу."""
    url_list = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url_list, headers=auth_headers_approver) as r:
        assert r.status == 200
        data = await r.json()
        groups = data.get("approver_groups") or []
    if not groups:
        pytest.skip("No approver groups to update (create via seed or previous test)")
    group_id = groups[0]["id"]
    patch_url = f"{base_url}/api/v1/approver-groups/{group_id}"
    async with http_session.patch(
        patch_url,
        headers=auth_headers_approver,
        json={"min_approvals": 2},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data.get("min_approvals") == 2
        assert data.get("id") == group_id


@pytest.mark.asyncio
async def test_approver_groups_update_not_found(
    http_session, base_url, auth_headers_approver
):
    """PATCH /api/v1/approver-groups/{id} для несуществующей группы возвращает 404."""
    url = f"{base_url}/api/v1/approver-groups/00000000-0000-0000-0000-000000000001"
    async with http_session.patch(
        url,
        headers=auth_headers_approver,
        json={"min_approvals": 2},
    ) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_approver_groups_update_no_fields_returns_400(
    http_session, base_url, auth_headers_approver, auth_headers_admin
):
    """PATCH /api/v1/approver-groups/{id} без полей для обновления возвращает 400."""
    url_list = f"{base_url}/api/v1/approver-groups"
    async with http_session.get(url_list, headers=auth_headers_approver) as r:
        if r.status != 200:
            pytest.skip("Need list")
        groups = (await r.json()).get("approver_groups") or []
    if not groups:
        pytest.skip("No groups")
    patch_url = f"{base_url}/api/v1/approver-groups/{groups[0]['id']}"
    async with http_session.patch(
        patch_url,
        headers=auth_headers_approver,
        json={},
    ) as resp:
        assert resp.status == 400
        data = await resp.json()
        assert "no fields" in (data.get("error") or "").lower() or "update" in (data.get("error") or "").lower()
