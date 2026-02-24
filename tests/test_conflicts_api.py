import uuid

import pytest
from conftest import create_experiment_in_running


async def _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_id: str) -> dict:
    url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        return {
            "experiment_id": exp_id,
            "flag_id": data["flag_id"],
            "flag_key": data["flag_key"],
        }


async def _create_domain(
    http_session,
    base_url,
    auth_headers_experimenter,
    key_prefix: str,
    default_policy: str,
) -> dict:
    url = f"{base_url}/api/v1/conflict-domains"
    key = f"{key_prefix}_{uuid.uuid4().hex[:12]}"
    payload = {
        "key": key,
        "name": f"Domain {key}",
        "description": "Conflict test domain",
        "default_policy": default_policy,
    }
    async with http_session.post(url, headers=auth_headers_experimenter, json=payload) as resp:
        assert resp.status == 201, await resp.text()
        return await resp.json()


async def _bind_experiment(
    http_session,
    base_url,
    auth_headers_experimenter,
    experiment_id: str,
    domain_id: str,
    policy: str,
    priority_tier: int | None = None,
    bid_value: float = 0,
) -> dict:
    url = f"{base_url}/api/v1/experiments/{experiment_id}/conflict-bindings"
    payload = {
        "domain_id": domain_id,
        "policy": policy,
        "priority_tier": priority_tier,
        "bid_value": bid_value,
        "is_enabled": True,
    }
    async with http_session.post(url, headers=auth_headers_experimenter, json=payload) as resp:
        assert resp.status == 200, await resp.text()
        return await resp.json()


async def _decide_for_flags(
    http_session,
    base_url,
    auth_headers_viewer,
    subject_id: str,
    flag_keys: list[str],
) -> dict:
    url = f"{base_url}/api/v1/decide"
    payload = {
        "subject_id": subject_id,
        "attributes": {},
        "flags": flag_keys,
    }
    async with http_session.post(url, headers=auth_headers_viewer, json=payload) as resp:
        assert resp.status == 200, await resp.text()
        return await resp.json()


@pytest.mark.asyncio
async def test_conflict_domain_crud_and_bindings_api(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_admin,
):
    exp_id = await create_experiment_in_running(
        http_session,
        base_url,
        auth_headers_experimenter,
        auth_headers_approver,
        auth_headers_admin,
        key_prefix="conflict_crud",
    )

    domain = await _create_domain(
        http_session,
        base_url,
        auth_headers_experimenter,
        key_prefix="checkout",
        default_policy="mutual_exclusion",
    )
    domain_id = domain["id"]

    list_url = f"{base_url}/api/v1/conflict-domains"
    async with http_session.get(list_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert any(d["id"] == domain_id for d in data["conflict_domains"])

    get_url = f"{base_url}/api/v1/conflict-domains/{domain_id}"
    async with http_session.get(get_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data["id"] == domain_id
        assert data["default_policy"] == "mutual_exclusion"

    async with http_session.patch(
        get_url,
        headers=auth_headers_experimenter,
        json={"default_policy": "priority", "description": "Updated policy"},
    ) as resp:
        assert resp.status == 200, await resp.text()
        updated = await resp.json()
        assert updated["default_policy"] == "priority"
        assert updated["config_version"] >= 2

    binding = await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_id,
        domain_id=domain_id,
        policy="priority",
        priority_tier=7,
    )
    assert binding["experiment_id"] == exp_id
    assert binding["domain_id"] == domain_id
    assert binding["policy"] == "priority"
    assert binding["priority_tier"] == 7

    bindings_url = f"{base_url}/api/v1/experiments/{exp_id}/conflict-bindings"
    async with http_session.get(bindings_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert len(data["bindings"]) >= 1
        assert any(b["domain_id"] == domain_id for b in data["bindings"])

    delete_binding_url = f"{base_url}/api/v1/experiments/{exp_id}/conflict-bindings/{domain_id}"
    async with http_session.delete(delete_binding_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 204

    async with http_session.delete(get_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 204


@pytest.mark.asyncio
async def test_conflicts_mutual_exclusion_deterministic_with_audit(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_admin,
    auth_headers_viewer,
):
    exp_a = await create_experiment_in_running(
        http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin, key_prefix="conflict_me_a"
    )
    exp_b = await create_experiment_in_running(
        http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin, key_prefix="conflict_me_b"
    )
    ctx_a = await _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_a)
    ctx_b = await _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_b)
    by_flag_key = {
        ctx_a["flag_key"]: ctx_a["experiment_id"],
        ctx_b["flag_key"]: ctx_b["experiment_id"],
    }

    domain = await _create_domain(
        http_session, base_url, auth_headers_experimenter, key_prefix="surface", default_policy="mutual_exclusion"
    )
    await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_a,
        domain_id=domain["id"],
        policy="mutual_exclusion",
    )
    await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_b,
        domain_id=domain["id"],
        policy="mutual_exclusion",
    )

    subject_id = "conflict-mutual-user-1"
    first = await _decide_for_flags(
        http_session,
        base_url,
        auth_headers_viewer,
        subject_id=subject_id,
        flag_keys=[ctx_a["flag_key"], ctx_b["flag_key"]],
    )
    second = await _decide_for_flags(
        http_session,
        base_url,
        auth_headers_viewer,
        subject_id=subject_id,
        flag_keys=[ctx_a["flag_key"], ctx_b["flag_key"]],
    )

    lost_first = [item for item in first["flags"] if item.get("conflict_lost") is True]
    lost_second = [item for item in second["flags"] if item.get("conflict_lost") is True]
    assert len(lost_first) == 1
    assert len(lost_second) == 1
    assert lost_first[0]["flag_key"] == lost_second[0]["flag_key"]
    assert lost_first[0]["conflict_domain"] == domain["key"]
    assert lost_second[0]["conflict_domain"] == domain["key"]

    loser_flag_key = lost_first[0]["flag_key"]
    loser_exp_id = by_flag_key[loser_flag_key]
    log_url = f"{base_url}/api/v1/experiments/{loser_exp_id}/conflict-log?limit=20"
    async with http_session.get(log_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200, await resp.text()
        decisions = (await resp.json()).get("decisions") or []
        assert any(d.get("won") is False for d in decisions)


@pytest.mark.asyncio
async def test_conflicts_priority_policy_prefers_higher_tier(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_admin,
    auth_headers_viewer,
):
    exp_low = await create_experiment_in_running(
        http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin, key_prefix="conflict_prio_low"
    )
    exp_high = await create_experiment_in_running(
        http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin, key_prefix="conflict_prio_high"
    )
    low_ctx = await _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_low)
    high_ctx = await _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_high)

    domain = await _create_domain(
        http_session, base_url, auth_headers_experimenter, key_prefix="priority", default_policy="priority"
    )
    await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_low,
        domain_id=domain["id"],
        policy="priority",
        priority_tier=1,
    )
    await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_high,
        domain_id=domain["id"],
        policy="priority",
        priority_tier=9,
    )

    decision = await _decide_for_flags(
        http_session,
        base_url,
        auth_headers_viewer,
        subject_id="conflict-priority-user",
        flag_keys=[low_ctx["flag_key"], high_ctx["flag_key"]],
    )
    by_key = {item["flag_key"]: item for item in decision["flags"]}
    assert by_key[low_ctx["flag_key"]]["conflict_lost"] is True
    assert by_key[low_ctx["flag_key"]]["conflict_domain"] == domain["key"]
    assert not by_key[high_ctx["flag_key"]].get("conflict_lost", False)


@pytest.mark.asyncio
async def test_conflicts_bid_policy_and_preflight_visibility(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_admin,
    auth_headers_viewer,
):
    exp_low_bid = await create_experiment_in_running(
        http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin, key_prefix="conflict_bid_low"
    )
    exp_high_bid = await create_experiment_in_running(
        http_session, base_url, auth_headers_experimenter, auth_headers_approver, auth_headers_admin, key_prefix="conflict_bid_high"
    )
    low_ctx = await _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_low_bid)
    high_ctx = await _get_experiment_ctx(http_session, base_url, auth_headers_experimenter, exp_high_bid)

    domain = await _create_domain(
        http_session, base_url, auth_headers_experimenter, key_prefix="bid", default_policy="bid"
    )
    await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_low_bid,
        domain_id=domain["id"],
        policy="bid",
        bid_value=0,
    )
    await _bind_experiment(
        http_session,
        base_url,
        auth_headers_experimenter,
        experiment_id=exp_high_bid,
        domain_id=domain["id"],
        policy="bid",
        bid_value=100,
    )

    preflight_url = f"{base_url}/api/v1/experiments/{exp_low_bid}/conflict-preflight"
    async with http_session.get(preflight_url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200, await resp.text()
        warnings = (await resp.json()).get("conflict_warnings") or []
        assert any(w.get("domain_key") == domain["key"] for w in warnings)
        domain_warning = next(w for w in warnings if w.get("domain_key") == domain["key"])
        assert any(c.get("experiment_id") == exp_high_bid for c in domain_warning["conflicting_experiments"])

    decision = await _decide_for_flags(
        http_session,
        base_url,
        auth_headers_viewer,
        subject_id="conflict-bid-user",
        flag_keys=[low_ctx["flag_key"], high_ctx["flag_key"]],
    )
    by_key = {item["flag_key"]: item for item in decision["flags"]}
    assert by_key[low_ctx["flag_key"]]["conflict_lost"] is True
    assert by_key[low_ctx["flag_key"]]["conflict_domain"] == domain["key"]
    assert not by_key[high_ctx["flag_key"]].get("conflict_lost", False)
