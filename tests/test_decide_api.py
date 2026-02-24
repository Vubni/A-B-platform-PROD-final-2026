import uuid

import pytest

DECIDE_URL_SUFFIX = "/api/v1/decide"


@pytest.mark.asyncio
async def test_decide_requires_auth(http_session, base_url):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-123",
        "attributes": {},
        "flags": ["some_flag_key"],
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_decide_forbidden_for_admin(http_session, base_url, auth_headers_admin, flag_key):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-123",
        "attributes": {},
        "flags": [flag_key],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_admin) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_decide_forbidden_for_experimenter(http_session, base_url, auth_headers_experimenter, flag_key):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-123",
        "attributes": {},
        "flags": [flag_key],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_experimenter) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_decide_success_viewer(http_session, base_url, auth_headers_viewer, flag_key):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "subject-test-001",
        "attributes": {"country": "RU"},
        "flags": [flag_key],
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
    http_session, base_url, auth_headers_viewer, auth_headers_admin, flag_key
):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    flags_list_url = f"{base_url}/api/v1/flags"
    async with http_session.get(flags_list_url, headers=auth_headers_admin) as r:
        if r.status != 200:
            pytest.skip("Need to list flags")
        flags_data = await r.json()
        flag = next((f for f in (flags_data.get("flags") or []) if f.get("key") == flag_key), None)
    if not flag:
        pytest.skip("Flag not found")
    expected_default = flag.get("default_value") or "control"
    payload = {
        "subject_id": "user-default-check",
        "attributes": {},
        "flags": [flag_key],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["flags"]) == 1
        assert data["flags"][0]["flag_value"] == expected_default
        assert data["flags"][0]["experiment"] is None


@pytest.mark.asyncio
async def test_decide_same_subject_same_value(
    http_session, base_url, auth_headers_viewer, flag_key
):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "consistent-user-42",
        "attributes": {"region": "eu"},
        "flags": [flag_key],
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
async def test_decide_returns_default_when_targeting_rule_not_matched(
    http_session,
    base_url,
    auth_headers_viewer,
    auth_headers_admin,
    auth_headers_experimenter,
    auth_headers_approver,
):
    flags_url = f"{base_url}/api/v1/flags"
    exp_url = f"{base_url}/api/v1/experiments"
    decide_url = f"{base_url}{DECIDE_URL_SUFFIX}"
    users_url = f"{base_url}/api/v1/users"

    async with http_session.get(users_url, headers=auth_headers_admin) as resp:
        if resp.status != 200:
            pytest.skip("Need admin to list users")
        users = (await resp.json()).get("users") or []
    experimenter = next((u for u in users if u.get("email") == "experimenter@test.com"), None)
    approver_user = next((u for u in users if u.get("email") == "approver@test.com"), None)
    if not experimenter or not approver_user:
        pytest.skip("Need experimenter and approver in seed")
    experimenter_id, approver_id = experimenter["id"], approver_user["id"]

    targeting_flag_key = f"decide_targeting_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={
            "key": targeting_flag_key,
            "value_type": "string",
            "default_value": "default_outside",
        },
    ) as resp:
        if resp.status not in (200, 201):
            pytest.skip("Could not create flag for targeting test")
        flag_data = await resp.json()
        flag_id = flag_data["id"]

    async with http_session.post(
        f"{base_url}/api/v1/approver-groups",
        headers=auth_headers_admin,
        json={
            "experimenter_id": experimenter_id,
            "min_approvals": 1,
            "approver_ids": [approver_id],
        },
    ) as grp:
        if grp.status not in (200, 201, 409):
            pytest.skip("Could not create approver group")

    async with http_session.post(
        exp_url,
        headers=auth_headers_experimenter,
        json={
            "flag_id": flag_id,
            "name": "Decide targeting test",
            "audience_fraction": 1.0,
            "targeting_rule": 'country == "RU"',
        },
    ) as resp:
        if resp.status != 201:
            pytest.skip(f"Could not create experiment: {await resp.text()}")
        exp = await resp.json()
        exp_id = exp["id"]

    for variant in [
        {"variant_name": "control", "variant_value": "default_outside", "weight": 0.5, "is_control": True},
        {"variant_name": "treatment", "variant_value": "treatment_val", "weight": 0.5, "is_control": False},
    ]:
        async with http_session.post(
            f"{base_url}/api/v1/experiments/{exp_id}/variants",
            headers=auth_headers_experimenter,
            json=variant,
        ) as r:
            if r.status != 201:
                pytest.skip("Could not add variant")

    from conftest import transition_experiment_to_running

    if not await transition_experiment_to_running(
        http_session, base_url, exp_id, auth_headers_experimenter, auth_headers_approver
    ):
        pytest.skip("Could not set status running")

    payload = {
        "subject_id": "user-outside-targeting",
        "attributes": {"country": "BY"},
        "flags": [targeting_flag_key],
    }
    async with http_session.post(decide_url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["flags"]) == 1
        assert data["flags"][0]["flag_value"] == "default_outside"
        assert data["flags"][0]["experiment"] is None

    payload_match = {
        "subject_id": "user-inside-targeting",
        "attributes": {"country": "RU"},
        "flags": [targeting_flag_key],
    }
    async with http_session.post(decide_url, json=payload_match, headers=auth_headers_viewer) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["flags"]) == 1
        assert data["flags"][0]["experiment"] is not None

    async with http_session.post(
        f"{base_url}/api/v1/experiments/{exp_id}/complete",
        headers=auth_headers_experimenter,
        json={"completion_outcome": "rollback", "comment": "Teardown targeting test"},
    ):
        pass


@pytest.mark.asyncio
async def test_decide_validation_empty_subject_id(http_session, base_url, auth_headers_viewer, flag_key):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "   ",
        "attributes": {},
        "flags": [flag_key],
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
async def test_decide_validation_empty_flag_key(http_session, base_url, auth_headers_viewer):
    url = f"{base_url}{DECIDE_URL_SUFFIX}"
    payload = {
        "subject_id": "user-1",
        "attributes": {},
        "flags": [""],
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
        "flags": ["nonexistent_flag_key_12345"],
    }
    async with http_session.post(url, json=payload, headers=auth_headers_viewer) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_decide_response_order_matches_request(
    http_session, base_url, auth_headers_viewer, auth_headers_admin, flag_key
):
    url_flags = f"{base_url}/api/v1/flags"
    url_decide = f"{base_url}{DECIDE_URL_SUFFIX}"
    second_key = f"decide_order_second_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        url_flags,
        headers=auth_headers_admin,
        json={
            "key": second_key,
            "value_type": "string",
            "default_value": "second_default",
        },
    ) as resp:
        if resp.status not in (200, 201):
            pytest.skip("Could not create second flag")
        await resp.json()
    payload = {
        "subject_id": "order-check",
        "attributes": {},
        "flags": [flag_key, second_key],
    }
    async with http_session.post(
        url_decide, json=payload, headers=auth_headers_viewer
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["flags"]) == 2
        assert data["flags"][0]["flag_key"] == "test_feature_flag"
        assert data["flags"][1]["flag_key"] == second_key
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

    audience_flag_key = f"decide_audience_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={
            "key": audience_flag_key,
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
        headers=auth_headers_admin,
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

    from conftest import transition_experiment_to_running

    if not await transition_experiment_to_running(
        http_session, base_url, exp_id, auth_headers_experimenter, auth_headers_approver
    ):
        audience_flag_key = f"decide_audience_{uuid.uuid4().hex[:12]}"
        async with http_session.post(
            flags_url,
            headers=auth_headers_admin,
            json={"key": audience_flag_key, "value_type": "string", "default_value": "default"},
        ) as resp:
            if resp.status not in (200, 201):
                pytest.skip("Could not create second flag for audience test")
            flag_id = (await resp.json())["id"]
        async with http_session.post(
            exp_url,
            headers=auth_headers_experimenter,
            json={"flag_id": flag_id, "name": "Decide audience 20% test (retry)", "audience_fraction": 0.2},
        ) as resp:
            if resp.status != 201:
                pytest.skip(f"Could not create retry experiment: {await resp.text()}")
            exp_id = (await resp.json())["id"]
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
                    pytest.skip("Could not add variant on retry")
        ok = await transition_experiment_to_running(
            http_session, base_url, exp_id, auth_headers_experimenter, auth_headers_approver
        )
        if not ok:
            pytest.skip("Could not set status running (another experiment on flag)")

    in_experiment = 0
    n = 50
    for i in range(n):
        payload = {
            "subject_id": f"audience-subject-{i}",
            "attributes": {},
            "flags": [audience_flag_key],
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
    async with http_session.post(
        f"{base_url}/api/v1/experiments/{exp_id}/complete",
        headers=auth_headers_experimenter,
        json={"completion_outcome": "rollback", "comment": "Teardown after audience test"},
    ) as _:
        pass
