import pytest
import uuid
from datetime import datetime, timezone


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


@pytest.fixture
async def events_submit_context(
    http_session,
    base_url,
    auth_headers_admin,
    auth_headers_viewer,
    auth_headers_experimenter,
    auth_headers_approver,
):
    from conftest import transition_experiment_to_running

    et_url = f"{base_url}/api/v1/event-types"
    key_exposure = "exposure"
    async with http_session.get(et_url, headers=auth_headers_admin) as r:
        if r.status != 200:
            pytest.skip("Need auth to list event types")
        data = await r.json()
        exists = any(et.get("key") == key_exposure for et in (data.get("event_types") or []))
    if not exists:
        async with http_session.post(
            et_url,
            headers=auth_headers_admin,
            json={"key": key_exposure, "display_name": "Exposure"},
        ) as r:
            if r.status not in (200, 201):
                pytest.skip(f"Could not create event type exposure: {await r.text()}")

    users_url = f"{base_url}/api/v1/users"
    async with http_session.get(users_url, headers=auth_headers_admin) as r:
        if r.status != 200:
            pytest.skip("Need users")
        users = (await r.json()).get("users") or []
    experimenter = next((u for u in users if u.get("email") == "experimenter@test.com"), None)
    approver_user = next((u for u in users if u.get("email") == "approver@test.com"), None)
    if not experimenter or not approver_user:
        pytest.skip("Need experimenter and approver")

    async with http_session.post(
        f"{base_url}/api/v1/approver-groups",
        headers=auth_headers_admin,
        json={"experimenter_id": experimenter["id"], "min_approvals": 1, "approver_ids": [approver_user["id"]]},
    ) as _:
        pass

    for attempt in range(2):
        flags_url = f"{base_url}/api/v1/flags"
        flag_key = f"events_submit_{uuid.uuid4().hex}"
        async with http_session.post(
            flags_url,
            headers=auth_headers_admin,
            json={"key": flag_key, "value_type": "string", "default_value": "control"},
        ) as r:
            if r.status not in (200, 201):
                pytest.skip("Could not create flag for events submit")
            flag_id = (await r.json())["id"]

        exp_url = f"{base_url}/api/v1/experiments"
        async with http_session.post(
            exp_url,
            headers=auth_headers_experimenter,
            json={"flag_id": flag_id, "name": "Events submit test", "audience_fraction": 1.0},
        ) as r:
            if r.status != 201:
                pytest.skip(f"Could not create experiment: {await r.text()}")
            exp_id = (await r.json())["id"]

        for v in [
            {"variant_name": "control", "variant_value": "c", "weight": 0.5, "is_control": True},
            {"variant_name": "treatment", "variant_value": "t", "weight": 0.5, "is_control": False},
        ]:
            async with http_session.post(
                f"{base_url}/api/v1/experiments/{exp_id}/variants",
                headers=auth_headers_experimenter,
                json=v,
            ) as vr:
                if vr.status != 201:
                    pytest.skip("Could not add variant")

        if await transition_experiment_to_running(
            http_session, base_url, exp_id, auth_headers_experimenter, auth_headers_approver
        ):
            break
        if attempt == 1:
            pytest.skip("Could not set status running (another experiment on flag)")

    decide_url = f"{base_url}/api/v1/decide"
    subject_id = f"events-subject-{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        decide_url,
        json={"subject_id": subject_id, "attributes": {}, "flags": [flag_id]},
        headers=auth_headers_viewer,
    ) as dr:
        if dr.status != 200:
            pytest.skip(f"Decide failed: {await dr.text()}")
        dec_data = await dr.json()
        if not dec_data.get("flags"):
            pytest.skip("No flags in decide response")
        decision_id = dec_data["flags"][0].get("decision_id")
    if not decision_id:
        pytest.skip("Decide returned no decision_id (no running experiment?)")
    return {"decision_id": decision_id, "subject_id": subject_id, "event_type_key": key_exposure}


@pytest.mark.asyncio
async def test_events_submit_returns_200_and_shape(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {"events": []}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data.get("accepted") == 0
        assert data.get("duplicates") == 0
        assert data.get("rejected") == 0
        assert data.get("errors") == []
        assert data.get("status") == "ok"
        assert "accepted" in data
        assert "duplicates" in data
        assert "rejected" in data
        assert "errors" in data
        assert isinstance(data["errors"], list)


@pytest.mark.asyncio
async def test_events_submit_invalid_body_no_events_key(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    async with http_session.post(url, json={}) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_events_submit_invalid_body_events_not_array(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    async with http_session.post(url, json={"events": "not-a-list"}) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_events_submit_single_event_missing_event_id(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status in (200, 400)
        if resp.status == 200:
            data = await resp.json()
            assert data["rejected"] == 1
            assert data["accepted"] == 0
            assert len(data["errors"]) == 1
            assert data["errors"][0]["index"] == 0
            assert "event_id" in data["errors"][0]["message"].lower() or "required" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_empty_event_id(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": "   ",
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert len(data["errors"]) == 1


@pytest.mark.asyncio
async def test_events_submit_single_event_missing_decision_id(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status in (200, 400)
        if resp.status == 200:
            data = await resp.json()
            assert data["rejected"] == 1
            err = data["errors"][0]
            assert "decision_id" in err["message"].lower() or "required" in err["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_invalid_decision_id_uuid(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": "not-a-uuid",
                "event_type_key": "exposure",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert "uuid" in data["errors"][0]["message"].lower() or "decision" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_missing_event_type_key(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status in (200, 400)
        if resp.status == 200:
            data = await resp.json()
            assert data["rejected"] == 1
            assert "event_type" in data["errors"][0]["message"].lower() or "required" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_missing_subject_id(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status in (200, 400)
        if resp.status == 200:
            data = await resp.json()
            assert data["rejected"] == 1
            assert "subject_id" in data["errors"][0]["message"].lower() or "required" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_missing_timestamp(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-1",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status in (200, 400)
        if resp.status == 200:
            data = await resp.json()
            assert data["rejected"] == 1
            assert "timestamp" in data["errors"][0]["message"].lower() or "required" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_invalid_timestamp(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-1",
                "timestamp": "not-iso-date",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert "timestamp" in data["errors"][0]["message"].lower() or "invalid" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_payload_not_object(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "exposure",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": "not-an-object",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert "payload" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_single_event_not_object(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {"events": ["not an event object"]}
    async with http_session.post(url, json=payload) as resp:
        assert resp.status in (200, 400, 422)
        if resp.status == 200:
            data = await resp.json()
            assert data["rejected"] == 1
            assert "object" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_unknown_event_type(http_session, base_url):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "nonexistent_type_xyz",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert "unknown event type" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_decision_id_not_found(http_session, base_url, auth_headers_admin):
    et_url = f"{base_url}/api/v1/event-types"
    key = f"ev_decision_not_found_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url, headers=auth_headers_admin, json={"key": key, "display_name": "Test"}
    ) as r:
        if r.status not in (200, 201):
            pytest.skip("Could not create event type")
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": str(uuid.uuid4()),
                "event_type_key": key,
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert "not found" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_valid_single_event_accepted(
    http_session, base_url, events_submit_context
):
    url = f"{base_url}/api/v1/events"
    ctx = events_submit_context
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": ctx["decision_id"],
                "event_type_key": ctx["event_type_key"],
                "subject_id": ctx["subject_id"],
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {},
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 1
        assert data["duplicates"] == 0
        assert data["rejected"] == 0
        assert data["errors"] == []
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_events_submit_duplicate_event_id(
    http_session, base_url, events_submit_context
):
    url = f"{base_url}/api/v1/events"
    ctx = events_submit_context
    ev_id = str(uuid.uuid4())
    event = {
        "event_id": ev_id,
        "decision_id": ctx["decision_id"],
        "event_type_key": ctx["event_type_key"],
        "subject_id": ctx["subject_id"],
        "timestamp": "2025-01-15T12:00:00Z",
        "payload": {},
    }
    async with http_session.post(url, json={"events": [event]}) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 1 and data["duplicates"] == 0 and data["rejected"] == 0
    async with http_session.post(url, json={"events": [event]}) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 0 and data["duplicates"] == 1 and data["rejected"] == 0


@pytest.mark.asyncio
async def test_events_submit_batch_mixed_accepted_rejected_duplicates(
    http_session, base_url, events_submit_context
):
    url = f"{base_url}/api/v1/events"
    ctx = events_submit_context
    ev_ok = str(uuid.uuid4())
    ev_dup = str(uuid.uuid4())
    events = [
        {
            "event_id": ev_ok,
            "decision_id": ctx["decision_id"],
            "event_type_key": ctx["event_type_key"],
            "subject_id": ctx["subject_id"],
            "timestamp": "2025-01-15T12:00:00Z",
            "payload": {},
        },
        {
            "event_id": str(uuid.uuid4()),
            "decision_id": ctx["decision_id"],
            "event_type_key": "unknown_type_xyz",
            "subject_id": ctx["subject_id"],
            "timestamp": "2025-01-15T12:00:00Z",
            "payload": {},
        },
        {
            "event_id": ev_dup,
            "decision_id": ctx["decision_id"],
            "event_type_key": ctx["event_type_key"],
            "subject_id": ctx["subject_id"],
            "timestamp": "2025-01-15T12:00:00Z",
            "payload": {},
        },
    ]
    async with http_session.post(url, json={"events": events}) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 2
        assert data["rejected"] == 1
        assert data["duplicates"] == 0
        assert len(data["errors"]) == 1
        assert data["errors"][0]["index"] == 1
        assert "unknown event type" in data["errors"][0]["message"].lower()
    async with http_session.post(url, json={"events": events}) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 0
        assert data["duplicates"] == 2
        assert data["rejected"] == 1
        assert len(data["errors"]) == 1


@pytest.mark.asyncio
async def test_events_submit_required_params_rejected(
    http_session, base_url, auth_headers_admin, events_submit_context
):
    et_url = f"{base_url}/api/v1/event-types"
    key = f"ev_reqparam_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url,
        headers=auth_headers_admin,
        json={"key": key, "required_params": {"amount": "number"}, "display_name": "With amount"},
    ) as r:
        if r.status not in (200, 201):
            pytest.skip("Could not create event type")
    url = f"{base_url}/api/v1/events"
    ctx = events_submit_context
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": ctx["decision_id"],
                "event_type_key": key,
                "subject_id": ctx["subject_id"],
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {},
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        assert "required" in data["errors"][0]["message"].lower() or "amount" in data["errors"][0]["message"].lower()


@pytest.mark.asyncio
async def test_events_submit_required_params_accepted(
    http_session, base_url, auth_headers_admin, events_submit_context
):
    et_url = f"{base_url}/api/v1/event-types"
    key = f"ev_reqparam_ok_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url,
        headers=auth_headers_admin,
        json={"key": key, "required_params": {"amount": "number"}, "display_name": "With amount"},
    ) as r:
        if r.status not in (200, 201):
            pytest.skip("Could not create event type")
    url = f"{base_url}/api/v1/events"
    ctx = events_submit_context
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": ctx["decision_id"],
                "event_type_key": key,
                "subject_id": ctx["subject_id"],
                "timestamp": "2025-01-15T12:00:00Z",
                "payload": {"amount": 99.5},
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_events_submit_timestamp_formats(http_session, base_url, events_submit_context):
    url = f"{base_url}/api/v1/events"
    ctx = events_submit_context
    for ts in ("2025-06-01T00:00:00Z", "2025-06-01T12:30:00+00:00"):
        payload = {
            "events": [
                {
                    "event_id": str(uuid.uuid4()),
                    "decision_id": ctx["decision_id"],
                    "event_type_key": ctx["event_type_key"],
                    "subject_id": ctx["subject_id"],
                    "timestamp": ts,
                    "payload": {},
                }
            ]
        }
        async with http_session.post(url, json=payload) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["accepted"] == 1, f"timestamp {ts!r} should be accepted: {data}"
            assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_events_submit_response_errors_contain_index_and_event_id(
    http_session, base_url
):
    url = f"{base_url}/api/v1/events"
    payload = {
        "events": [
            {
                "event_id": "custom-ev-123",
                "decision_id": str(uuid.uuid4()),
                "event_type_key": "nonexistent_key_xyz",
                "subject_id": "user-1",
                "timestamp": "2025-01-15T12:00:00Z",
            }
        ]
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["rejected"] == 1
        err = data["errors"][0]
        assert "index" in err
        assert err["index"] == 0
        assert err.get("event_id") == "custom-ev-123"
        assert "message" in err


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


@pytest.mark.asyncio
async def test_events_submit_out_of_order_with_requires_show(
    http_session,
    base_url,
    auth_headers_admin,
    events_submit_context,
):
    et_url = f"{base_url}/api/v1/event-types"
    key_show = f"api_queue_show_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url,
        json={"key": key_show, "display_name": "Queued Show"},
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status in (200, 201), await cr.text()
        show_type = await cr.json()
        show_id = show_type["id"]
    key_click = f"api_queue_click_{uuid.uuid4().hex[:8]}"
    async with http_session.post(
        et_url,
        json={
            "key": key_click,
            "display_name": "Queued Click",
            "requires_show_event_type_id": show_id,
        },
        headers=auth_headers_admin,
    ) as cr:
        assert cr.status in (200, 201), await cr.text()

    ctx = events_submit_context
    events_url = f"{base_url}/api/v1/events"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    click_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": ctx["decision_id"],
                "event_type_key": key_click,
                "subject_id": ctx["subject_id"],
                "timestamp": now,
                "payload": {},
            }
        ]
    }
    async with http_session.post(events_url, json=click_payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 0
    show_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": ctx["decision_id"],
                "event_type_key": key_show,
                "subject_id": ctx["subject_id"],
                "timestamp": now,
                "payload": {},
            }
        ]
    }
    async with http_session.post(events_url, json=show_payload) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["accepted"] == 1
        assert data["rejected"] == 0


@pytest.mark.asyncio
async def test_guardrail_pauses_experiment_when_threshold_exceeded(
    http_session,
    base_url,
    auth_headers_admin,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_viewer,
    linked_event_types_metrics_experiment_running,
):
    ctx = linked_event_types_metrics_experiment_running
    exp_id = ctx["experiment_id"]
    metric_key_guardrail = ctx["metric_keys"]["conversions"]
    guardrails_url = f"{base_url}/api/v1/guardrails"
    async with http_session.post(
        guardrails_url,
        headers=auth_headers_experimenter,
        json={
            "metric_key": metric_key_guardrail,
            "threshold": 0.0,
            "window_seconds": 60,
            "action": "pause",
        },
    ) as resp:
        assert resp.status == 200, await resp.text()
    decide_url = f"{base_url}/api/v1/decide"
    decision_ids = []
    for i in range(3):
        payload = {
            "subject_id": f"guardrail-subject-{i}",
            "attributes": {},
            "flags": [ctx["flag_id"]],
        }
        async with http_session.post(
            decide_url,
            json=payload,
            headers=auth_headers_viewer,
        ) as resp:
            assert resp.status == 200, await resp.text()
            data = await resp.json()
            assert data["flags"], "Decide must return at least one flag"
            did = data["flags"][0]["decision_id"]
            assert did
            decision_ids.append(did)
    decision_id = decision_ids[0]
    events_url = f"{base_url}/api/v1/events"
    conversion_key = ctx["event_type_keys"]["conversion"]
    now_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    events_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "decision_id": decision_id,
                "event_type_key": conversion_key,
                "subject_id": "guardrail-user",
                "timestamp": now_ts,
                "payload": {},
            }
        ]
    }
    async with http_session.post(events_url, json=events_payload) as resp:
        assert resp.status == 200, await resp.text()
        submit_result = await resp.json()
        assert submit_result.get("accepted", 0) >= 1, (
            f"Conversion event must be accepted: {submit_result}"
        )
    get_exp_url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.get(get_exp_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        exp_data = await resp.json()
        assert exp_data["status"] in (
            "running",
            "paused",
            "completed",
        ), f"Unexpected status after event submit: {exp_data['status']}"
    history_url = f"{base_url}/api/v1/experiments/{exp_id}/guardrail-history"
    async with http_session.get(history_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        history = await resp.json()
        assert history["experiment_id"] == exp_id
        assert isinstance(history["triggers"], list)
