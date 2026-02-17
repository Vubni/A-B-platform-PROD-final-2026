import pytest


@pytest.mark.asyncio
async def test_experiments_list_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/experiments"
    async with http_session.get(url) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_experiments_list_success(http_session, base_url, auth_headers_experimenter):
    url = f"{base_url}/api/v1/experiments"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "experiments" in data
        assert isinstance(data["experiments"], list)


@pytest.mark.asyncio
async def test_experiments_list_filter_by_status(http_session, base_url, auth_headers_experimenter):
    url = f"{base_url}/api/v1/experiments?status=draft"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "experiments" in data


@pytest.mark.asyncio
async def test_experiments_create_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": "00000000-0000-0000-0000-000000000000",
        "name": "Unauth experiment",
        "audience_fraction": 0.5,
    }
    async with http_session.post(url, json=payload) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_experiments_create_success(http_session, base_url, auth_headers_experimenter, flag_id):
    url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": flag_id,
        "name": "Test experiment from API test",
        "audience_fraction": 0.5,
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 201
        data = await resp.json()
        assert data["name"] == "Test experiment from API test"
        assert data["status"] == "draft"
        assert data["audience_fraction"] == 0.5
        assert data["flag_id"] == flag_id
        assert "id" in data
        assert "variants" in data
        assert "flag_key" in data


@pytest.mark.asyncio
async def test_experiments_create_invalid_flag_returns_404(http_session, base_url, auth_headers_experimenter):
    url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": "00000000-0000-0000-0000-000000000000",
        "name": "No flag",
        "audience_fraction": 0.5,
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_experiments_create_validation_error(http_session, base_url, auth_headers_experimenter, flag_id):
    """POST /api/v1/experiments с audience_fraction > 1 возвращает 400."""
    url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": flag_id,
        "name": "Bad fraction",
        "audience_fraction": 1.5,
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_experiments_get_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001"
    async with http_session.get(url) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_experiments_get_not_found(http_session, base_url, auth_headers_experimenter):
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_experiments_get_success(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """Создаём эксперимент и получаем его по ID."""
    create_url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": flag_id,
        "name": "Get test experiment",
        "audience_fraction": 0.3,
    }
    async with http_session.post(
        create_url, json=payload, headers=auth_headers_experimenter
    ) as create_resp:
        assert create_resp.status == 201
        created = await create_resp.json()
        exp_id = created["id"]

    get_url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.get(get_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == exp_id
        assert data["name"] == "Get test experiment"
        assert data["status"] == "draft"
        assert "variants" in data
        assert "flag_key" in data


@pytest.mark.asyncio
async def test_experiments_update_success(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """PATCH /api/v1/experiments/{id} в draft обновляет название и долю аудитории."""
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={
            "flag_id": flag_id,
            "name": "To update",
            "audience_fraction": 0.2,
        },
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]

    patch_url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.patch(
        patch_url,
        json={"name": "Updated name", "audience_fraction": 0.4},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["name"] == "Updated name"
        assert data["audience_fraction"] == 0.4
        assert data.get("version", 1) >= 1


@pytest.mark.asyncio
async def test_experiments_update_not_draft_returns_400(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """После перевода в on_review обновление полей эксперимента возвращает 400."""
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={
            "flag_id": flag_id,
            "name": "To send to review",
            "audience_fraction": 0.5,
        },
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]

    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    async with http_session.post(
        var_url,
        json={
            "variant_name": "control",
            "variant_value": "control",
            "weight": 0.25,
            "is_control": True,
        },
        headers=auth_headers_experimenter,
    ) as vr:
        assert vr.status == 201
    async with http_session.post(
        var_url,
        json={
            "variant_name": "treatment",
            "variant_value": "treatment",
            "weight": 0.25,
            "is_control": False,
        },
        headers=auth_headers_experimenter,
    ) as vr:
        assert vr.status == 201

    status_url = f"{base_url}/api/v1/experiments/{exp_id}/status"
    async with http_session.patch(
        status_url,
        json={"status": "on_review"},
        headers=auth_headers_experimenter,
    ) as sr:
        assert sr.status == 200

    patch_url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.patch(
        patch_url,
        json={"name": "Should fail"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 400


@pytest.mark.asyncio
async def test_experiments_variant_add_and_list(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """Добавление вариантов к эксперименту в draft и проверка через GET."""
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={
            "flag_id": flag_id,
            "name": "Experiment with variants",
            "audience_fraction": 0.5,
        },
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        created = await cr.json()
        exp_id = created["id"]

    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    async with http_session.post(
        var_url,
        json={
            "variant_name": "control",
            "variant_value": "control",
            "weight": 0.5,
            "is_control": True,
        },
        headers=auth_headers_experimenter,
    ) as vr:
        assert vr.status == 201
        v = await vr.json()
        assert v["variant_name"] == "control"
        assert v["is_control"] is True
        variant_id = v["id"]

    async with http_session.post(
        var_url,
        json={
            "variant_name": "treatment",
            "variant_value": "treatment",
            "weight": 0.0,
            "is_control": False,
        },
        headers=auth_headers_experimenter,
    ) as vr:
        assert vr.status == 201

    get_url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.get(get_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["variants"]) == 2
        names = {v["variant_name"] for v in data["variants"]}
        assert names == {"control", "treatment"}

    patch_var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants/{variant_id}"
    async with http_session.patch(
        patch_var_url,
        json={"weight": 0.5, "variant_value": "control_v2"},
        headers=auth_headers_experimenter,
    ) as pr:
        assert pr.status == 200
        updated = await pr.json()
        assert updated["variant_value"] == "control_v2"
        assert updated["weight"] == 0.5

    treatment_id = next(
        v["id"] for v in data["variants"] if v["variant_name"] == "treatment"
    )
    delete_var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants/{treatment_id}"
    async with http_session.delete(
        delete_var_url, headers=auth_headers_experimenter
    ) as dr:
        assert dr.status == 204

    async with http_session.get(get_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data2 = await resp.json()
        assert len(data2["variants"]) == 1
        assert data2["variants"][0]["variant_name"] == "control"


@pytest.mark.asyncio
async def test_experiments_status_transition_to_on_review(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """PATCH status на on_review после добавления вариантов возвращает 200."""
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={
            "flag_id": flag_id,
            "name": "Status transition test",
            "audience_fraction": 0.5,
        },
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]

    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    for name, value, weight, control in [
        ("control", "c", 0.25, True),
        ("treatment", "t", 0.25, False),
    ]:
        async with http_session.post(
            var_url,
            json={
                "variant_name": name,
                "variant_value": value,
                "weight": weight,
                "is_control": control,
            },
            headers=auth_headers_experimenter,
        ) as vr:
            assert vr.status == 201

    status_url = f"{base_url}/api/v1/experiments/{exp_id}/status"
    async with http_session.patch(
        status_url,
        json={"status": "on_review"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "on_review"


@pytest.mark.asyncio
async def test_experiments_guardrail_history(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """GET /api/v1/experiments/{id}/guardrail-history возвращает 200 и triggers."""
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={
            "flag_id": flag_id,
            "name": "Guardrail history test",
            "audience_fraction": 0.5,
        },
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]

    url = f"{base_url}/api/v1/experiments/{exp_id}/guardrail-history"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["experiment_id"] == exp_id
        assert "triggers" in data
        assert isinstance(data["triggers"], list)


@pytest.mark.asyncio
async def test_experiments_guardrail_history_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """GET guardrail-history для несуществующего эксперимента — 404."""
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/guardrail-history"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404
