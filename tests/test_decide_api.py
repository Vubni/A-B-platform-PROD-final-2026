import pytest


DECIDE_URL_SUFFIX = "/api/v1/decide"


@pytest.mark.asyncio
async def test_decide_requires_auth(http_session, base_url):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-123",
        "attributes": {},
        "flags": ["00000000-0000-0000-0000-000000000001"],
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_decide_forbidden_for_admin(http_session, base_url, auth_headers_admin, flag_id):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-123",
        "attributes": {},
        "flags": [flag_id],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_admin) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_decide_forbidden_for_experimenter(http_session, base_url, auth_headers_experimenter, flag_id):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-123",
        "attributes": {},
        "flags": [flag_id],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_experimenter) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_decide_success_viewer(http_session, base_url, auth_headers_viewer, flag_id):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "subject-test-001",
        "attributes": {"country": "RU"},
        "flags": [flag_id],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)
        assert len(data["flags"]) == 1
        item = data["flags"][0]
        assert "flag_key" in item
        assert "flag_value" in item
        assert "decision_id" in item
        assert item.get("experiment") is None or (
            isinstance(item["experiment"], dict)
            and "experiment_id" in item["experiment"]
            and "variant" in item["experiment"]
        )


@pytest.mark.asyncio
async def test_decide_returns_default_value_when_no_experiment(
    http_session, base_url, auth_headers_viewer, auth_headers_admin, flag_id
):
    """Decide возвращает default_value флага, когда субъект не в эксперименте."""
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    flags_list_url = f"{base_url}/api/v1/flags"
    async with http_session.get(flags_list_url, headers=auth_headers_admin) as r:
        if r.status != 200:
            pytest.skip("Need to list flags")
        flags_data = await r.json()
        flag = next((f for f in (flags_data.get("flags") or []) if f.get("id") == flag_id), None)
    if not flag:
        pytest.skip("Flag not found")
    expected_default = flag.get("default_value") or "control"
    payload = {
        "subject_id": "user-default-check",
        "attributes": {},
        "flags": [flag_id],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["flags"]) == 1
        assert data["flags"][0]["flag_value"] == expected_default
        assert data["flags"][0]["experiment"] is None


@pytest.mark.asyncio
async def test_decide_same_subject_same_value(
    http_session, base_url, auth_headers_viewer, flag_id
):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "consistent-user-42",
        "attributes": {"region": "eu"},
        "flags": [flag_id],
    }
    values = []
    for _ in range(5):
        async with http_session.post(
            url, json=payload, headers=auth_headers_viewer
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert len(data["flags"]) == 1
            values.append(data["flags"][0]["flag_value"])
    assert len(set(values)) == 1, f"Ожидалось одно значение для одного субъекта, получено: {values}"


@pytest.mark.asyncio
async def test_decide_validation_empty_subject_id(http_session, base_url, auth_headers_viewer, flag_id):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "   ",
        "attributes": {},
        "flags": [flag_id],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 422
        data = await resp.json()
        assert data.get("code") == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_decide_validation_empty_flags(http_session, base_url, auth_headers_viewer):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-1",
        "attributes": {},
        "flags": [],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 422
        data = await resp.json()
        assert data.get("code") == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_decide_validation_invalid_flag_uuid(http_session, base_url, auth_headers_viewer):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-1",
        "attributes": {},
        "flags": ["not-a-uuid"],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 422
        data = await resp.json()
        assert data.get("code") == "VALIDATION_FAILED"


@pytest.mark.asyncio
async def test_decide_flag_not_found(http_session, base_url, auth_headers_viewer):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-1",
        "attributes": {},
        "flags": ["00000000-0000-0000-0000-000000000099"],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_decide_response_order_matches_request(
    http_session, base_url, auth_headers_viewer, auth_headers_admin, flag_id
):
    url_flags = f"{base_url}/api/v1/flags"
    url_decide = f"{base_url}{DECIDE_URL_SUFFIX}"
    async with http_session.post(
        url_flags,
        headers=auth_headers_admin,
        json={
            "key": "decide_order_second",
            "value_type": "string",
            "default_value": "second_default",
        },
    ) as resp:
        if resp.status not in (200, 201):
            pytest.skip("Could not create second flag")
        second = await resp.json()
        second_id = second["id"]
    payload = {
        "subject_id": "order-check",
        "attributes": {},
        "flags": [flag_id, second_id],
    }
    async with http_session.post(
        url_decide, json=payload, headers=auth_headers_viewer
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["flags"]) == 2
        assert data["flags"][0]["flag_key"] == "test_feature_flag"
        assert data["flags"][1]["flag_key"] == "decide_order_second"
        assert data["flags"][0]["flag_value"] == "control"
        assert data["flags"][1]["flag_value"] == "second_default"


@pytest.mark.asyncio
async def test_decide_audience_fraction_about_20_percent(
    http_session,
    base_url,
    auth_headers_admin,
    auth_headers_viewer,
    auth_headers_experimenter,
    auth_headers_approver,
):
    users_url = f"{base_url}/api/v1/users"
    flags_url = f"{base_url}/api/v1/flags"
    exp_url = f"{base_url}/api/v1/experiments"
    decide_url = f"{base_url}{DECIDE_URL_SUFFIX}"

    async with http_session.get(users_url, headers=auth_headers_admin) as resp:
        if resp.status != 200:
            pytest.skip("Need admin to list users")
        users = (await resp.json()).get("users") or []
    experimenter = next((u for u in users if u.get("email") == "experimenter@test.com"), None)
    approver_user = next((u for u in users if u.get("email") == "approver@test.com"), None)
    if not experimenter or not approver_user:
        pytest.skip("Need experimenter and approver in seed")
    experimenter_id, approver_id = experimenter["id"], approver_user["id"]

    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={
            "key": "decide_audience_test",
            "value_type": "string",
            "default_value": "default",
        },
    ) as resp:
        if resp.status not in (200, 201):
            pytest.skip("Could not create flag for audience test")
        flag_data = await resp.json()
        flag_id = flag_data["id"]

    async with http_session.post(
        f"{base_url}/api/v1/approver-groups",
        headers=auth_headers_approver,
        json={
            "experimenter_id": experimenter_id,
            "min_approvals": 1,
            "approver_ids": [approver_id],
        },
    ) as grp:
        if grp.status not in (200, 201, 409):
            pytest.skip(f"Could not create approver group: {grp.status} {await grp.text()}")

    async with http_session.post(
        exp_url,
        headers=auth_headers_experimenter,
        json={
            "flag_id": flag_id,
            "name": "Decide audience 20% test",
            "audience_fraction": 0.2,
        },
    ) as resp:
        if resp.status != 201:
            pytest.skip(f"Could not create experiment: {await resp.text()}")
        exp = await resp.json()
        exp_id = exp["id"]

    for variant in [
        {"variant_name": "control", "variant_value": "default", "weight": 0.1, "is_control": True},
        {"variant_name": "treatment", "variant_value": "treatment_val", "weight": 0.1, "is_control": False},
    ]:
        async with http_session.post(
            f"{base_url}/api/v1/experiments/{exp_id}/variants",
            headers=auth_headers_experimenter,
            json=variant,
        ) as r:
            if r.status != 201:
                pytest.skip("Could not add variant")

    for status, role in [("on_review", auth_headers_experimenter), ("approved", auth_headers_approver), ("running", auth_headers_experimenter)]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=role,
            json={"status": status},
        ) as r:
            if r.status != 200:
                pytest.skip(f"Could not set status {status}: {await r.text()}")

    in_experiment = 0
    n = 50
    for i in range(n):
        payload = {
            "subject_id": f"audience-subject-{i}",
            "attributes": {},
            "flags": [flag_id],
        }
        async with http_session.post(decide_url, json=payload, headers=auth_headers_viewer) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert len(data["flags"]) == 1
            if data["flags"][0].get("experiment") is not None:
                in_experiment += 1

    ratio = in_experiment / n
    assert 0.12 <= ratio <= 0.30, (
        f"Ожидалось ~20% в эксперименте (audience_fraction=0.2), получено {ratio:.1%} ({in_experiment}/{n})"
    )
