import pytest
import uuid


@pytest.mark.asyncio
async def test_event_types_list_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/event-types"
    async with http_session.get(url) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_event_types_list_success(http_session, base_url, auth_headers_admin):
    url = f"{base_url}/api/v1/event-types"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "event_types" in data
        assert isinstance(data["event_types"], list)


@pytest.mark.asyncio
async def test_event_types_list_filter_status(
    http_session, base_url, auth_headers_admin
):
    url_active = f"{base_url}/api/v1/event-types?status=active"
    async with http_session.get(url_active, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "event_types" in data
        for et in data["event_types"]:
            assert et.get("status") == "active"

    url_archived = f"{base_url}/api/v1/event-types?status=archived"
    async with http_session.get(url_archived, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "event_types" in data
        for et in data["event_types"]:
            assert et.get("status") == "archived"


@pytest.mark.asyncio
async def test_event_types_list_as_viewer(http_session, base_url, auth_headers_viewer):
    url = f"{base_url}/api/v1/event-types"
    async with http_session.get(url, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "event_types" in data


@pytest.mark.asyncio
async def test_event_types_create_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/event-types"
    payload = {"key": "auth_test_event_type"}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_event_types_create_forbidden_for_non_admin(
    http_session, base_url, auth_headers_experimenter
):
    url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_experimenter_{uuid.uuid4().hex[:8]}"
    payload = {"key": key, "display_name": "By Experimenter"}
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_event_types_create_success(http_session, base_url, auth_headers_admin):
    url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_{uuid.uuid4().hex[:8]}"
    payload = {
        "key": key,
        "display_name": "Test Event Type",
        "description": "Created by events API test",
        "is_critical": False,
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["key"] == key
        assert data.get("display_name") == "Test Event Type"
        assert data.get("description") == "Created by events API test"
        assert data.get("status") == "active"
        assert data.get("is_critical") is False
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.asyncio
async def test_event_types_create_with_optional_fields(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_full_{uuid.uuid4().hex[:8]}"
    payload = {
        "key": key,
        "display_name": "Full Event Type",
        "required_params": {"amount": "number"},
        "validation_type": "schema",
        "report_alert_config": {"metric_key": "conversion"},
        "is_critical": True,
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 201, f"Expected 201, got {resp.status}"
        data = await resp.json()
        assert data is not None, "API returned 201 with null body"
        assert data["key"] == key
        assert data.get("is_critical") is True
        assert data.get("required_params") == {"amount": "number"}
        assert data.get("validation_type") == "schema"
        assert data.get("report_alert_config") == {"metric_key": "conversion"}


@pytest.mark.asyncio
async def test_event_types_create_duplicate_key_returns_409(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_dup_{uuid.uuid4().hex[:8]}"
    payload = {"key": key}
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as cr:
        assert cr.status == 201
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 409
        data = await resp.json()
        assert data.get("code") == "KEY_ALREADY_EXISTS" or "key" in (data.get("details") or {})


@pytest.mark.asyncio
async def test_event_types_create_invalid_key_returns_400(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types"
    async with http_session.post(
        url, json={"key": ""}, headers=auth_headers_admin
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_event_types_create_requires_show_valid_uuid(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_rs_{uuid.uuid4().hex[:8]}"
    payload = {"key": key, "requires_show_event_type_id": "not-a-uuid"}
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_event_types_get_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/event-types/{uuid.uuid4()}"
    async with http_session.get(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_event_types_get_success(
    http_session, base_url, auth_headers_admin
):
    create_url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_get_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url,
        json={"key": key, "display_name": "Get Me"},
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status == 201
        created = await cr.json()
        type_id = created["id"]

    get_url = f"{base_url}/api/v1/event-types/{type_id}"
    async with http_session.get(get_url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == type_id
        assert data["key"] == key
        assert data.get("display_name") == "Get Me"


@pytest.mark.asyncio
async def test_event_types_get_not_found(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types/{uuid.uuid4()}"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_event_types_get_invalid_id_returns_404(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types/not-a-uuid"
    async with http_session.get(url, headers=auth_headers_admin) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_event_types_update_success(
    http_session, base_url, auth_headers_admin
):
    create_url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_patch_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url,
        json={"key": key, "display_name": "Original"},
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status == 201
        created = await cr.json()
        type_id = created["id"]

    patch_url = f"{base_url}/api/v1/event-types/{type_id}"
    async with http_session.patch(
        patch_url,
        json={
            "display_name": "Updated Name",
            "description": "Updated description",
            "is_critical": True,
        },
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["display_name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["is_critical"] is True
        assert data["key"] == key


@pytest.mark.asyncio
async def test_event_types_update_forbidden_for_non_admin(
    http_session, base_url, auth_headers_admin, auth_headers_experimenter
):
    create_url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_patch_perm_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url, json={"key": key}, headers=auth_headers_admin
    ) as cr:
        assert cr.status == 201
        type_id = (await cr.json())["id"]

    patch_url = f"{base_url}/api/v1/event-types/{type_id}"
    async with http_session.patch(
        patch_url,
        json={"display_name": "Hacked"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_event_types_update_not_found(
    http_session, base_url, auth_headers_admin
):      
    url = f"{base_url}/api/v1/event-types/{uuid.uuid4()}"
    async with http_session.patch(
        url,
        json={"display_name": "X"},
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_event_types_archive_success(
    http_session, base_url, auth_headers_admin
):
    create_url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_archive_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url, json={"key": key}, headers=auth_headers_admin
    ) as cr:
        assert cr.status == 201
        created = await cr.json()
        type_id = created["id"]

    delete_url = f"{base_url}/api/v1/event-types/{type_id}"
    async with http_session.delete(delete_url, headers=auth_headers_admin) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == type_id
        assert data["status"] == "archived"

    async with http_session.get(
        f"{base_url}/api/v1/event-types?status=archived",
        headers=auth_headers_admin,
    ) as r:
        list_data = await r.json()
        ids = [et["id"] for et in list_data["event_types"]]
        assert type_id in ids


@pytest.mark.asyncio
async def test_event_types_archive_forbidden_for_non_admin(
    http_session, base_url, auth_headers_admin, auth_headers_viewer
):
    create_url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_arch_perm_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url, json={"key": key}, headers=auth_headers_admin
    ) as cr:
        assert cr.status == 201
        type_id = (await cr.json())["id"]

    delete_url = f"{base_url}/api/v1/event-types/{type_id}"
    async with http_session.delete(delete_url, headers=auth_headers_viewer) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_event_types_archive_not_found(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types/{uuid.uuid4()}"
    async with http_session.delete(url, headers=auth_headers_admin) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_event_types_create_with_requires_show(
    http_session, base_url, auth_headers_admin
):
    create_url = f"{base_url}/api/v1/event-types"
    key_show = f"api_show_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url,
        json={"key": key_show, "display_name": "Show event"},
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status == 201
        show_type = await cr.json()
        show_id = show_type["id"]

    key_click = f"api_click_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        create_url,
        json={
            "key": key_click,
            "display_name": "Click event",
            "requires_show_event_type_id": show_id,
        },
        headers=auth_headers_admin,
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["requires_show_event_type_id"] == show_id


@pytest.mark.asyncio
async def test_event_types_create_requires_show_nonexistent_returns_400(
    http_session, base_url, auth_headers_admin
):
    url = f"{base_url}/api/v1/event-types"
    key = f"api_test_et_rs_bad_{uuid.uuid4().hex[:8]}"
    payload = {"key": key, "requires_show_event_type_id": str(uuid.uuid4())}
    async with http_session.post(
        url, json=payload, headers=auth_headers_admin
    ) as resp:
        assert resp.status == 400
        data = await resp.json()
        assert "requires_show" in (data.get("message") or "").lower() or "BAD_REQUEST" in (data.get("code") or "")


@pytest.mark.asyncio
async def test_events_submit_returns_200_and_shape(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {"events": []}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "accepted" in data
        assert "duplicates" in data
        assert "rejected" in data
        assert "errors" in data
        assert isinstance(data["errors"], list)
        assert "status" in data


@pytest.mark.asyncio
async def test_events_submit_with_events_body(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-123",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {},
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "accepted" in data
        assert "duplicates" in data
        assert "rejected" in data
        assert "errors" in data
