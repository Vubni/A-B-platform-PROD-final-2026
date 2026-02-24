import uuid

import pytest


@pytest.mark.asyncio
async def test_learnings_list_requires_auth(http_session, base_url):
    async with http_session.get(f"{base_url}/api/v1/learnings") as resp:
        assert resp.status == 401


@pytest.mark.asyncio
async def test_learning_upsert_and_get_by_experiment(
    http_session, base_url, auth_headers_experimenter, flag_id
):
    create_exp_url = f"{base_url}/api/v1/experiments"
    async with http_session.post(
        create_exp_url,
        headers=auth_headers_experimenter,
        json={"flag_id": flag_id, "name": "Learning API test", "audience_fraction": 0.5},
    ) as resp:
        assert resp.status == 201, await resp.text()
        exp = await resp.json()
        exp_id = exp["id"]

    upsert_url = f"{base_url}/api/v1/experiments/{exp_id}/learning"
    payload = {
        "hypothesis": "Добавление блока рекомендаций увеличит конверсию в клик",
        "primary_metric_key": "ctr",
        "result_outcome": "no_effect",
        "result_action": "repeat",
        "effect_summary": "+0.3% (стат. незначимо)",
        "targeting_summary": "ios + android, RU, новые пользователи",
        "platforms": ["ios", "android"],
        "countries": ["RU"],
        "product_tags": ["search", "recommendations"],
        "change_type": "ui_banner",
        "variant_structure": {"kind": "ab", "weights": [0.5, 0.5]},
        "notes": "На старых версиях app был перекос трафика в control",
        "is_completed": True,
        "guardrails": [{"metric_key": "p95_latency", "threshold_value": 350, "trigger_count": 1}],
    }
    async with http_session.put(upsert_url, headers=auth_headers_experimenter, json=payload) as resp:
        assert resp.status == 200, await resp.text()
        learning = await resp.json()
        assert learning["experiment_id"] == exp_id
        learning_id = learning["id"]

    async with http_session.get(
        f"{base_url}/api/v1/experiments/{exp_id}/learning",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200
        learning_by_exp = await resp.json()
        assert learning_by_exp["id"] == learning_id
        assert learning_by_exp["is_completed"] is True

    async with http_session.get(
        f"{base_url}/api/v1/learnings/{learning_id}",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200
        direct = await resp.json()
        assert direct["id"] == learning_id
        assert direct["result_outcome"] == "no_effect"


@pytest.mark.asyncio
async def test_learning_audit_and_similar(
    http_session, base_url, auth_headers_experimenter, auth_headers_admin
):
    flag_keys = ["learn_a", "learn_b"]
    suffix = uuid.uuid4().hex[:8]
    exp_ids = []
    for key in flag_keys:
        async with http_session.post(
            f"{base_url}/api/v1/flags",
            headers=auth_headers_admin,
            json={"key": f"{key}_{suffix}", "value_type": "string", "default_value": "c"},
        ) as f_resp:
            assert f_resp.status == 201, await f_resp.text()
            flag = await f_resp.json()
        async with http_session.post(
            f"{base_url}/api/v1/experiments",
            headers=auth_headers_experimenter,
            json={
                "flag_id": flag["id"],
                "name": f"Learning {key}",
                "audience_fraction": 0.5,
            },
        ) as e_resp:
            assert e_resp.status == 201, await e_resp.text()
            exp_ids.append((await e_resp.json())["id"])

    base_payload = {
        "hypothesis": "Упростить путь до целевого действия",
        "primary_metric_key": "conversion_rate",
        "result_outcome": "rollback",
        "result_action": "rollback",
        "platforms": ["web"],
        "countries": ["RU", "KZ"],
        "product_tags": ["checkout", "conversion"],
        "change_type": "ui_flow",
        "notes": "Guardrail по latency срабатывал в прайм-тайм",
        "is_completed": True,
        "guardrails": [{"metric_key": "p95_latency", "threshold_value": 500, "trigger_count": 2}],
    }

    learning_ids = []
    for exp_id in exp_ids:
        async with http_session.put(
            f"{base_url}/api/v1/experiments/{exp_id}/learning",
            headers=auth_headers_experimenter,
            json=base_payload,
        ) as resp:
            assert resp.status == 200, await resp.text()
            learning_ids.append((await resp.json())["id"])

    payload_update = dict(base_payload)
    payload_update["notes"] = "Обновлённый вывод после повторной проверки сегмента"
    async with http_session.put(
        f"{base_url}/api/v1/experiments/{exp_ids[0]}/learning",
        headers=auth_headers_experimenter,
        json=payload_update,
    ) as resp:
        assert resp.status == 200

    async with http_session.get(
        f"{base_url}/api/v1/learnings/{learning_ids[0]}/audit",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert data["learning_id"] == learning_ids[0]
        assert isinstance(data["audit"], list)
        assert len(data["audit"]) >= 1
        actions = {item.get("action") for item in data["audit"]}
        assert "update" in actions or "insert" in actions
        if any(str(a).startswith("guardrail_") for a in actions if a):
            assert (
                "guardrail_insert" in actions
                or "guardrail_update" in actions
                or "guardrail_delete" in actions
            )

    async with http_session.get(
        f"{base_url}/api/v1/learnings/{learning_ids[0]}/similar?limit=5",
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert data["learning_id"] == learning_ids[0]
        assert isinstance(data["similar"], list)
        if data["similar"]:
            first = data["similar"][0]
            assert "reasons" in first
            assert isinstance(first["reasons"], list)
