import uuid

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
async def test_experiments_create_with_metrics_from_catalog(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": ctx["flag_id"],
        "name": "Experiment with linked metrics",
        "audience_fraction": 0.5,
        "metrics": [
            {"metric_key": ctx["metric_keys"]["conversion_rate"], "metric_type": "primary"},
            {"metric_key": ctx["metric_keys"]["impressions"], "metric_type": "auxiliary"},
            {"metric_key": ctx["metric_keys"]["conversions"], "metric_type": "guardrail"},
        ],
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 201, await resp.text()
        data = await resp.json()
        assert data["name"] == "Experiment with linked metrics"
        assert data["status"] == "draft"
        assert "metrics" in data
        metric_keys = [m["metric_key"] for m in data["metrics"]]
        assert ctx["metric_keys"]["conversion_rate"] in metric_keys
        assert ctx["metric_keys"]["impressions"] in metric_keys
        assert ctx["metric_keys"]["conversions"] in metric_keys
        primary = next(m for m in data["metrics"] if m.get("metric_type") == "primary")
        assert primary["metric_key"] == ctx["metric_keys"]["conversion_rate"]


@pytest.mark.asyncio
async def test_experiments_get_includes_metrics_from_catalog(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == ctx["experiment_id"]
        assert "metrics" in data
        assert len(data["metrics"]) >= 3
        keys = {m["metric_key"] for m in data["metrics"]}
        assert ctx["metric_keys"]["conversion_rate"] in keys
        assert ctx["metric_keys"]["impressions"] in keys
        assert ctx["metric_keys"]["conversions"] in keys
        assert "variants" in data
        assert len(data["variants"]) == 2


@pytest.mark.asyncio
async def test_experiments_create_metrics_not_in_catalog_returns_400(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    url = f"{base_url}/api/v1/experiments"
    payload = {
        "flag_id": flag_id,
        "name": "Bad metrics",
        "audience_fraction": 0.5,
        "metrics": [
            {"metric_key": "nonexistent_metric_xyz_123", "metric_type": "primary"},
            {"metric_key": "another_fake_metric", "metric_type": "auxiliary"},
        ],
    }
    async with http_session.post(
        url, json=payload, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 400
        data = await resp.json()
        assert "unknown_keys" in data or "error" in data
        if "unknown_keys" in data:
            assert "nonexistent_metric_xyz_123" in data["unknown_keys"]


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
async def test_experiments_variant_add_rejected_when_weights_sum_mismatch_audience_fraction(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={
            "flag_id": flag_id,
            "name": "Weights sum test",
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
            "variant_value": "c",
            "weight": 0.2,
            "is_control": True,
        },
        headers=auth_headers_experimenter,
    ) as vr:
        assert vr.status == 201

    async with http_session.post(
        var_url,
        json={
            "variant_name": "treatment",
            "variant_value": "t",
            "weight": 0.2,
            "is_control": False,
        },
        headers=auth_headers_experimenter,
    ) as vr:
        assert vr.status in (400, 500), "Ожидалось отклонение: сумма весов (0.4) не равна покрытию (0.5)"


@pytest.mark.asyncio
async def test_experiments_guardrail_history(
    http_session, base_url, auth_headers_experimenter, flag_id
):
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
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/guardrail-history"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_experiments_complete_requires_auth(http_session, base_url):
    """POST .../complete без токена возвращает 401."""
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/complete"
    async with http_session.post(
        url,
        json={"completion_outcome": "rollback", "comment": "Test"},
    ) as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_experiments_complete_forbidden_for_viewer(
    http_session, base_url, auth_headers_viewer, auth_headers_experimenter,
    auth_headers_approver, auth_headers_admin
):
    """POST .../complete от viewer возвращает 403."""
    flags_url = f"{base_url}/api/v1/flags"
    key = f"complete_perm_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={"key": key, "value_type": "string", "default_value": "c"},
    ) as fr:
        assert fr.status == 201
        flag_id = (await fr.json())["id"]
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={"flag_id": flag_id, "name": "Complete perm test", "audience_fraction": 0.5},
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]
    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    for v in [
        {"variant_name": "control", "variant_value": "c", "weight": 0.25, "is_control": True},
        {"variant_name": "treatment", "variant_value": "t", "weight": 0.25, "is_control": False},
    ]:
        async with http_session.post(var_url, headers=auth_headers_experimenter, json=v) as vr:
            assert vr.status == 201
    for status, headers in [
        ("on_review", auth_headers_experimenter),
        ("approved", auth_headers_approver),
        ("running", auth_headers_experimenter),
    ]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=headers,
            json={"status": status},
        ) as sr:
            assert sr.status == 200, f"Set {status}: {await sr.text()}"
    complete_url = f"{base_url}/api/v1/experiments/{exp_id}/complete"
    async with http_session.post(
        complete_url,
        headers=auth_headers_viewer,
        json={"completion_outcome": "rollback", "comment": "Viewer cannot complete"},
    ) as resp:
        assert resp.status == 403
        data = await resp.json()
        assert data.get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_experiments_complete_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """POST .../complete по несуществующему эксперименту возвращает 404."""
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/complete"
    async with http_session.post(
        url,
        headers=auth_headers_experimenter,
        json={"completion_outcome": "rollback", "comment": "Test"},
    ) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_experiments_complete_invalid_status_returns_400(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    """POST .../complete при статусе draft возвращает 400."""
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={"flag_id": flag_id, "name": "Draft complete test", "audience_fraction": 0.5},
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]
    complete_url = f"{base_url}/api/v1/experiments/{exp_id}/complete"
    async with http_session.post(
        complete_url,
        headers=auth_headers_experimenter,
        json={"completion_outcome": "rollback", "comment": "Cannot complete draft"},
    ) as resp:
        assert resp.status == 400
        data = await resp.json()
        assert "running" in (data.get("error") or "").lower() or "paused" in (data.get("error") or "").lower()


@pytest.mark.asyncio
async def test_experiments_complete_rollout_winner_invalid_variant_returns_400(
    http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin
):
    """POST .../complete с completion_outcome=rollout_winner и неверным variant_id возвращает 400."""
    flags_url = f"{base_url}/api/v1/flags"
    key = f"complete_invalid_var_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={"key": key, "value_type": "string", "default_value": "c"},
    ) as fr:
        assert fr.status == 201
        flag_id = (await fr.json())["id"]
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={"flag_id": flag_id, "name": "Rollout invalid variant", "audience_fraction": 0.5},
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]
    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    for v in [
        {"variant_name": "control", "variant_value": "c", "weight": 0.25, "is_control": True},
        {"variant_name": "treatment", "variant_value": "t", "weight": 0.25, "is_control": False},
    ]:
        async with http_session.post(var_url, headers=auth_headers_experimenter, json=v) as _:
            pass
    for status, headers in [
        ("on_review", auth_headers_experimenter),
        ("approved", auth_headers_approver),
        ("running", auth_headers_experimenter),
    ]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=headers,
            json={"status": status},
        ) as r:
            if r.status == 409:
                pytest.skip("Another experiment already running on this flag")
            assert r.status == 200, f"Failed to set {status}: {await r.text()}"
    complete_url = f"{base_url}/api/v1/experiments/{exp_id}/complete"
    async with http_session.post(
        complete_url,
        headers=auth_headers_experimenter,
        json={
            "completion_outcome": "rollout_winner",
            "completion_winner_variant_id": "00000000-0000-0000-0000-000000000099",
            "comment": "Invalid variant",
        },
    ) as resp:
        assert resp.status == 400
        data = await resp.json()
        err = (data.get("error") or "").lower()
        assert "variant" in err or "winner" in err or "experiment" in err


@pytest.mark.asyncio
async def test_experiments_complete_success_rollback(
    http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin
):
    """POST .../complete с rollback возвращает 200 и status=completed."""
    flags_url = f"{base_url}/api/v1/flags"
    key = f"complete_rollback_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={"key": key, "value_type": "string", "default_value": "c"},
    ) as fr:
        assert fr.status == 201
        flag_id = (await fr.json())["id"]
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={"flag_id": flag_id, "name": "Complete rollback test", "audience_fraction": 0.5},
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]
    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    for v in [
        {"variant_name": "control", "variant_value": "c", "weight": 0.25, "is_control": True},
        {"variant_name": "treatment", "variant_value": "t", "weight": 0.25, "is_control": False},
    ]:
        async with http_session.post(var_url, headers=auth_headers_experimenter, json=v) as _:
            pass
    for status, headers in [
        ("on_review", auth_headers_experimenter),
        ("approved", auth_headers_approver),
        ("running", auth_headers_experimenter),
    ]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=headers,
            json={"status": status},
        ) as r:
            if r.status == 409:
                pytest.skip("Another experiment already running on this flag")
            assert r.status == 200, f"Failed to set {status}: {await r.text()}"
    complete_url = f"{base_url}/api/v1/experiments/{exp_id}/complete"
    async with http_session.post(
        complete_url,
        headers=auth_headers_experimenter,
        json={"completion_outcome": "rollback", "comment": "Rollback to control"},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "completed"
        assert data["id"] == exp_id


@pytest.mark.asyncio
async def test_experiments_complete_success_no_effect(
    http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin
):
    """POST .../complete с no_effect возвращает 200."""
    flags_url = f"{base_url}/api/v1/flags"
    key = f"complete_no_effect_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={"key": key, "value_type": "string", "default_value": "c"},
    ) as fr:
        assert fr.status == 201
        flag_id = (await fr.json())["id"]
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={"flag_id": flag_id, "name": "Complete no_effect test", "audience_fraction": 0.5},
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]
    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    for v in [
        {"variant_name": "control", "variant_value": "c", "weight": 0.25, "is_control": True},
        {"variant_name": "treatment", "variant_value": "t", "weight": 0.25, "is_control": False},
    ]:
        async with http_session.post(var_url, headers=auth_headers_experimenter, json=v) as _:
            pass
    for status, headers in [
        ("on_review", auth_headers_experimenter),
        ("approved", auth_headers_approver),
        ("running", auth_headers_experimenter),
    ]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=headers,
            json={"status": status},
        ) as r:
            if r.status == 409:
                pytest.skip("Another experiment already running on this flag")
            assert r.status == 200, f"Failed to set {status}: {await r.text()}"
    complete_url = f"{base_url}/api/v1/experiments/{exp_id}/complete"
    async with http_session.post(
        complete_url,
        headers=auth_headers_experimenter,
        json={"completion_outcome": "no_effect", "comment": "No significant effect"},
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_experiments_complete_success_rollout_winner(
    http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin
):
    """POST .../complete с rollout_winner и валидным variant_id возвращает 200."""
    flags_url = f"{base_url}/api/v1/flags"
    key = f"complete_rollout_{uuid.uuid4().hex[:12]}"
    async with http_session.post(
        flags_url,
        headers=auth_headers_admin,
        json={"key": key, "value_type": "string", "default_value": "c"},
    ) as fr:
        assert fr.status == 201
        flag_id = (await fr.json())["id"]
    create_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_url,
        json={"flag_id": flag_id, "name": "Complete rollout test", "audience_fraction": 0.5},
        headers=auth_headers_experimenter,
    ) as cr:
        assert cr.status == 201
        exp_id = (await cr.json())["id"]
    var_url = f"{base_url}/api/v1/experiments/{exp_id}/variants"
    treatment_id = None
    for v in [
        {"variant_name": "control", "variant_value": "c", "weight": 0.25, "is_control": True},
        {"variant_name": "treatment", "variant_value": "t", "weight": 0.25, "is_control": False},
    ]:
        async with http_session.post(var_url, headers=auth_headers_experimenter, json=v) as vr:
            assert vr.status == 201
            if v["variant_name"] == "treatment":
                treatment_id = (await vr.json())["id"]
    for status, headers in [
        ("on_review", auth_headers_experimenter),
        ("approved", auth_headers_approver),
        ("running", auth_headers_experimenter),
    ]:
        async with http_session.patch(
            f"{base_url}/api/v1/experiments/{exp_id}/status",
            headers=headers,
            json={"status": status},
        ) as r:
            if r.status == 409:
                pytest.skip("Another experiment already running on this flag")
            assert r.status == 200, f"Failed to set {status}: {await r.text()}"
    complete_url = f"{base_url}/api/v1/experiments/{exp_id}/complete"
    async with http_session.post(
        complete_url,
        headers=auth_headers_experimenter,
        json={
            "completion_outcome": "rollout_winner",
            "completion_winner_variant_id": treatment_id,
            "comment": "Treatment wins",
        },
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "completed"
        assert data["id"] == exp_id
