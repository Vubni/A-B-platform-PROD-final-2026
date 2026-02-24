import pytest
from conftest import create_experiment_in_running

from database.database import Database
from functions.experiments import record_guardrail_trigger


def _assert_step_shape(step: dict):
    assert set(step.keys()) == {"step_index", "traffic_fraction"}


def _assert_safety_action_shape(action: dict):
    assert set(action.keys()) == {"trigger_type", "action", "notify"}


async def _get_experiment_flag_key(http_session, base_url, auth_headers_experimenter, exp_id: str) -> str:
    url = f"{base_url}/api/v1/experiments/{exp_id}"
    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        return data["flag_key"]


async def _decide_once(http_session, base_url, auth_headers_viewer, flag_key: str, subject_id: str):
    url = f"{base_url}/api/v1/decide"
    payload = {
        "subject_id": subject_id,
        "attributes": {},
        "flags": [flag_key],
    }
    async with http_session.post(url, headers=auth_headers_viewer, json=payload) as resp:
        assert resp.status == 200, await resp.text()


async def _rewind_last_eval_at(experiment_id: str):
    async with Database() as db:
        await db.execute(
            """UPDATE experiment_ramp_state
               SET last_eval_at = NOW() - INTERVAL '2 minutes',
                   updated_at = NOW()
               WHERE experiment_id = $1""",
            (experiment_id,),
        )


@pytest.fixture
async def running_experiment_id(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_approver,
    auth_headers_admin,
):
    return await create_experiment_in_running(
        http_session,
        base_url,
        auth_headers_experimenter,
        auth_headers_approver,
        auth_headers_admin,
        key_prefix="autopilot",
    )


@pytest.fixture
def ramp_plan_payload():
    return {
        "observation_window_seconds": 900,
        "steps": [
            {"step_index": 0, "traffic_fraction": 0.25},
            {"step_index": 1, "traffic_fraction": 0.5},
        ],
        "gate_data_sufficiency": {
            "min_total_impressions": 100,
            "min_impressions_per_variant": 50,
            "min_minutes_on_step": 15,
        },
        "gate_safety": {
            "use_guardrails": True,
            "error_rate_threshold": 0.05,
            "latency_p95_ms": 1200,
        },
        "gate_data_health": {
            "require_no_srm": True,
            "require_no_mass_rejected": True,
        },
        "safety_actions": [
            {"trigger_type": "guardrail_triggered", "action": "pause", "notify": True},
            {"trigger_type": "error_rate_high", "action": "step_back", "notify": False},
        ],
    }


@pytest.mark.asyncio
async def test_ramp_plan_put_get_contract_shape(
    http_session,
    base_url,
    auth_headers_experimenter,
    running_experiment_id,
    ramp_plan_payload,
):
    exp_id = running_experiment_id
    url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"

    async with http_session.put(url, headers=auth_headers_experimenter, json=ramp_plan_payload) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert data["experiment_id"] == exp_id
        assert data["observation_window_seconds"] == ramp_plan_payload["observation_window_seconds"]
        assert len(data["steps"]) == 2
        assert len(data["safety_actions"]) == 2
        for step in data["steps"]:
            _assert_step_shape(step)
        for action in data["safety_actions"]:
            _assert_safety_action_shape(action)

    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert data["experiment_id"] == exp_id
        for step in data["steps"]:
            _assert_step_shape(step)
        for action in data["safety_actions"]:
            _assert_safety_action_shape(action)


@pytest.mark.asyncio
async def test_ramp_plan_requires_experimenter_role(
    http_session,
    base_url,
    auth_headers_viewer,
    running_experiment_id,
    ramp_plan_payload,
):
    exp_id = running_experiment_id
    url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"

    async with http_session.put(url, headers=auth_headers_viewer, json=ramp_plan_payload) as resp:
        assert resp.status == 403


@pytest.mark.asyncio
async def test_ramp_start_mode_override_and_decision_log(
    http_session,
    base_url,
    auth_headers_experimenter,
    running_experiment_id,
    ramp_plan_payload,
):
    exp_id = running_experiment_id
    ramp_plan_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"
    start_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-start"
    mode_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-mode"
    override_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-override"
    state_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-state"
    log_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-decision-log?limit=10"

    async with http_session.put(
        ramp_plan_url, headers=auth_headers_experimenter, json=ramp_plan_payload
    ) as r_plan:
        assert r_plan.status == 200, await r_plan.text()

    async with http_session.post(start_url, headers=auth_headers_experimenter) as r_start:
        assert r_start.status == 200, await r_start.text()
        state = await r_start.json()
        assert state["experiment_id"] == exp_id
        assert state["mode"] == "autopilot"
        assert state["current_step_index"] == 0

    async with http_session.patch(
        mode_url, headers=auth_headers_experimenter, json={"mode": "manual"}
    ) as r_mode:
        assert r_mode.status == 200, await r_mode.text()
        state = await r_mode.json()
        assert state["mode"] == "manual"

    async with http_session.post(
        override_url, headers=auth_headers_experimenter, json={"to_step_index": 1}
    ) as r_override:
        assert r_override.status == 200, await r_override.text()
        state = await r_override.json()
        assert state["current_step_index"] == 1
        assert state["mode"] == "manual"

    async with http_session.get(state_url, headers=auth_headers_experimenter) as r_state:
        assert r_state.status == 200
        state = await r_state.json()
        assert state["current_step_index"] == 1
        assert state["mode"] == "manual"

    async with http_session.get(log_url, headers=auth_headers_experimenter) as r_log:
        assert r_log.status == 200
        data = await r_log.json()
        decisions = data.get("decisions") or []
        assert len(decisions) >= 3
        actions = {d.get("action") for d in decisions}
        assert "start" in actions
        assert "override" in actions


@pytest.mark.asyncio
async def test_ramp_override_rejected_in_autopilot_mode(
    http_session,
    base_url,
    auth_headers_experimenter,
    running_experiment_id,
    ramp_plan_payload,
):
    exp_id = running_experiment_id
    ramp_plan_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"
    start_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-start"
    override_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-override"

    async with http_session.put(
        ramp_plan_url, headers=auth_headers_experimenter, json=ramp_plan_payload
    ) as r_plan:
        assert r_plan.status == 200
    async with http_session.post(start_url, headers=auth_headers_experimenter) as r_start:
        assert r_start.status == 200
    async with http_session.post(
        override_url, headers=auth_headers_experimenter, json={"to_step_index": 1}
    ) as r_override:
        assert r_override.status == 400
        data = await r_override.json()
        assert "manual" in (data.get("error") or "").lower()


@pytest.mark.asyncio
async def test_ramp_plan_delete_flow(
    http_session,
    base_url,
    auth_headers_experimenter,
    running_experiment_id,
    ramp_plan_payload,
):
    exp_id = running_experiment_id
    url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"

    async with http_session.put(url, headers=auth_headers_experimenter, json=ramp_plan_payload) as resp:
        assert resp.status == 200

    async with http_session.delete(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 204

    async with http_session.get(url, headers=auth_headers_experimenter) as resp:
        assert resp.status == 404


@pytest.mark.asyncio
async def test_autopilot_steps_up_when_gates_pass(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_viewer,
    running_experiment_id,
):
    exp_id = running_experiment_id
    flag_key = await _get_experiment_flag_key(http_session, base_url, auth_headers_experimenter, exp_id)
    ramp_plan_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"
    start_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-start"
    state_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-state"
    log_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-decision-log?limit=20"

    plan = {
        "observation_window_seconds": 900,
        "steps": [
            {"step_index": 0, "traffic_fraction": 0.25},
            {"step_index": 1, "traffic_fraction": 0.5},
        ],
        "gate_data_sufficiency": {
            "min_total_impressions": 1,
            "min_impressions_per_variant": 0,
            "min_minutes_on_step": 0,
        },
        "safety_actions": [],
    }
    async with http_session.put(ramp_plan_url, headers=auth_headers_experimenter, json=plan) as r_plan:
        assert r_plan.status == 200, await r_plan.text()
    async with http_session.post(start_url, headers=auth_headers_experimenter) as r_start:
        assert r_start.status == 200, await r_start.text()

    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-up-1")
    await _rewind_last_eval_at(exp_id)
    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-up-2")
    await _rewind_last_eval_at(exp_id)
    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-up-3")

    async with http_session.get(state_url, headers=auth_headers_experimenter) as r_state:
        assert r_state.status == 200, await r_state.text()
        state = await r_state.json()
        assert state["current_step_index"] == 1
        assert state["mode"] == "autopilot"

    async with http_session.get(log_url, headers=auth_headers_experimenter) as r_log:
        assert r_log.status == 200, await r_log.text()
        log = (await r_log.json()).get("decisions") or []
        assert any(d.get("action") == "step_up" for d in log)


@pytest.mark.asyncio
async def test_autopilot_steps_back_when_guardrail_triggered(
    http_session,
    base_url,
    auth_headers_experimenter,
    auth_headers_viewer,
    running_experiment_id,
):
    exp_id = running_experiment_id
    flag_key = await _get_experiment_flag_key(http_session, base_url, auth_headers_experimenter, exp_id)
    ramp_plan_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-plan"
    start_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-start"
    state_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-state"
    log_url = f"{base_url}/api/v1/experiments/{exp_id}/ramp-decision-log?limit=20"

    plan = {
        "observation_window_seconds": 900,
        "steps": [
            {"step_index": 0, "traffic_fraction": 0.25},
            {"step_index": 1, "traffic_fraction": 0.5},
        ],
        "gate_data_sufficiency": {
            "min_total_impressions": 1,
            "min_impressions_per_variant": 0,
            "min_minutes_on_step": 0,
        },
        "safety_actions": [
            {"trigger_type": "guardrail_triggered", "action": "step_back", "notify": False},
        ],
    }
    async with http_session.put(ramp_plan_url, headers=auth_headers_experimenter, json=plan) as r_plan:
        assert r_plan.status == 200, await r_plan.text()
    async with http_session.post(start_url, headers=auth_headers_experimenter) as r_start:
        assert r_start.status == 200, await r_start.text()

    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-back-1")
    await _rewind_last_eval_at(exp_id)
    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-back-2")
    await _rewind_last_eval_at(exp_id)
    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-back-3")

    async with http_session.get(state_url, headers=auth_headers_experimenter) as r_state_before:
        assert r_state_before.status == 200, await r_state_before.text()
        state_before = await r_state_before.json()
        assert state_before["current_step_index"] == 1

    await record_guardrail_trigger(
        experiment_id=exp_id,
        metric_key="test_guardrail_for_autopilot",
        threshold=0.0,
        window_seconds=900,
        action="pause",
        metric_value=1.0,
        details='{"source":"autopilot-ramp-test"}',
    )
    await _rewind_last_eval_at(exp_id)
    await _decide_once(http_session, base_url, auth_headers_viewer, flag_key, "autopilot-back-4")

    async with http_session.get(state_url, headers=auth_headers_experimenter) as r_state_after:
        assert r_state_after.status == 200, await r_state_after.text()
        state_after = await r_state_after.json()
        assert state_after["current_step_index"] == 0
        assert state_after["mode"] == "autopilot"

    async with http_session.get(log_url, headers=auth_headers_experimenter) as r_log:
        assert r_log.status == 200, await r_log.text()
        log = (await r_log.json()).get("decisions") or []
        assert any(d.get("action") == "step_back" for d in log)
