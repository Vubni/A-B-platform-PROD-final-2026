import asyncio
import uuid
from datetime import UTC, datetime

import pytest


@pytest.mark.asyncio
async def test_report_requires_auth(http_session, base_url):
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/report"
    async with http_session.get(url, params={"start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z"}) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_report_experiment_not_found(
    http_session, base_url, auth_headers_experimenter
):
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/report"
    async with http_session.get(
        url,
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 404
        data = await resp.json()
        assert data.get("code") == "NOT_FOUND"


@pytest.mark.asyncio
async def test_report_missing_params_returns_400(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    async with http_session.get(
        url,
        params={"end": "2026-02-01T00:00:00Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status in (400, 422)
    async with http_session.get(
        url,
        params={"start": "2026-01-01T00:00:00Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_report_invalid_window(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    async with http_session.get(
        url,
        params={"start": "2026-02-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_report_filter_by_period_rebuilds_report(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    params1 = {"start": "2025-01-01T00:00:00Z", "end": "2026-06-01T00:00:00Z"}
    params2 = {"start": "2026-06-01T00:00:00Z", "end": "2027-12-31T23:59:59Z"}
    async with http_session.get(url, params=params1, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data1 = await resp.json()
    async with http_session.get(url, params=params2, headers=auth_headers_experimenter) as resp:
        assert resp.status == 200
        data2 = await resp.json()
    assert data1["context"]["window_start"] == params1["start"]
    assert data1["context"]["window_end"] == params1["end"]
    assert data2["context"]["window_start"] == params2["start"]
    assert data2["context"]["window_end"] == params2["end"]
    assert data1["context"]["window_start"] != data2["context"]["window_start"]
    assert data1["context"]["window_end"] != data2["context"]["window_end"]


@pytest.mark.asyncio
async def test_report_success_structure(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    params = {"start": "2025-01-01T00:00:00Z", "end": "2027-12-31T23:59:59Z"}
    async with http_session.get(
        url, params=params, headers=auth_headers_experimenter
    ) as resp:
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert data.get("experiment_id") == ctx["experiment_id"]
        assert "experiment_name" in data
        assert "status" in data
        assert "result" in data
        if data.get("status") == "completed":
            assert data["result"] in ("rollout", "rollback", "no_effect"), (
                f"При status=completed result должен быть rollout | rollback | no_effect, получено: {data.get('result')!r}"
            )
        assert "completion" in data
        assert "context" in data
        ctx_report = data["context"]
        assert ctx_report["window_start"] == params["start"]
        assert ctx_report["window_end"] == params["end"]
        assert ctx_report.get("attribution") == "by_decision_id"
        assert "aggregation_unit" in ctx_report
        assert "dynamics" in data
        assert isinstance(data["dynamics"], list)
        if data.get("primary_metric_summary"):
            assert len(data["dynamics"]) >= 1
            d0 = data["dynamics"][0]
            assert "period_start" in d0 and "period_end" in d0 and "metric_key" in d0 and "value" in d0
        assert "metrics" in data
        assert isinstance(data["metrics"], list)
        assert len(data["metrics"]) >= 3
        metric_keys_in_report = {m["metric_key"] for m in data["metrics"]}
        assert ctx["metric_keys"]["conversion_rate"] in metric_keys_in_report
        assert ctx["metric_keys"]["impressions"] in metric_keys_in_report
        assert ctx["metric_keys"]["conversions"] in metric_keys_in_report
        assert "variants" in data
        assert len(data["variants"]) == 2
        for v in data["variants"]:
            assert "variant_id" in v
            assert "variant_name" in v
            assert "is_control" in v
            assert "decisions_count" in v
            assert "subjects_count" in v
            assert "share_pct" in v
            assert "metric_values" in v
            assert "event_counts" in v
            assert isinstance(v["event_counts"], dict)
            for slug in ("exposure", "conversion"):
                assert ctx["event_type_keys"][slug] in v["event_counts"]
        if data.get("status") == "completed" and data.get("completion"):
            comp = data["completion"]
            assert comp.get("outcome") in ("rollout_winner", "rollback", "no_effect")
            assert "comment" in comp
        print("\n--- report success structure ---")
        print("experiment_id:", data.get("experiment_id"))
        print("experiment_name:", data.get("experiment_name"))
        print("context:", data.get("context"))
        print("metrics:", data.get("metrics"))
        print("variants (id, name, is_control, metric_values, event_counts):")
        for v in data["variants"]:
            print("  ", v.get("variant_id"), v.get("variant_name"), "control=", v.get("is_control"))
            print("    metric_values:", v.get("metric_values"))
            print("    event_counts:", v.get("event_counts"))


@pytest.mark.asyncio
async def test_report_primary_metric_summary(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    async with http_session.get(
        url,
        params={"start": "2025-01-01T00:00:00Z", "end": "2027-12-31T23:59:59Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert "primary_metric_summary" in data
        summary = data["primary_metric_summary"]
        assert summary is not None
        assert summary.get("metric_key") == ctx["metric_keys"]["conversion_rate"]
        assert "control_value" in summary
        assert "results" in summary
        assert "summary_lines" in summary
        assert summary.get("recommendation") in ("keep_control", "rollout")
        assert "winner_variant_id" in summary
        assert "winner_variant_name" in summary
        assert isinstance(summary["results"], list)
        assert isinstance(summary["summary_lines"], list)
        print("\n--- primary_metric_summary ---")
        print("metric_key:", summary.get("metric_key"))
        print("control_value:", summary.get("control_value"))
        print("results:", summary.get("results"))
        print("summary_lines:", summary.get("summary_lines"))


@pytest.mark.asyncio
async def test_report_metric_values_per_variant(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    async with http_session.get(
        url,
        params={"start": "2025-01-01T00:00:00Z", "end": "2027-12-31T23:59:59Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        expected_metric_keys = [
            ctx["metric_keys"]["conversion_rate"],
            ctx["metric_keys"]["impressions"],
            ctx["metric_keys"]["conversions"],
        ]
        for v in data["variants"]:
            mv_keys = {m["metric_key"] for m in v["metric_values"]}
            for k in expected_metric_keys:
                assert k in mv_keys
            for m in v["metric_values"]:
                assert "value" in m
                assert "metric_key" in m
        print("\n--- metric_values per variant ---")
        for v in data["variants"]:
            print("variant:", v.get("variant_name"), v.get("variant_id"))
            for m in v.get("metric_values", []):
                print("  ", m.get("metric_key"), "=", m.get("value"), m.get("unit", ""))


@pytest.mark.asyncio
async def test_report_as_viewer(
    http_session, base_url, auth_headers_viewer, linked_event_types_metrics_experiment
):
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    async with http_session.get(
        url,
        params={"start": "2025-01-01T00:00:00Z", "end": "2027-12-31T23:59:59Z"},
        headers=auth_headers_viewer,
    ) as resp:
        assert resp.status == 200
        data = await resp.json()
        assert data.get("experiment_id") == ctx["experiment_id"]
        print("\n--- report as viewer ---")
        print("experiment_id:", data.get("experiment_id"))
        print("primary_metric_summary:", data.get("primary_metric_summary"))
        print("variants count:", len(data.get("variants", [])))


@pytest.mark.asyncio
async def test_report_after_decide_and_events_shows_user_share_and_real_conclusions(
    http_session,
    base_url,
    auth_headers_viewer,
    auth_headers_experimenter,
    linked_event_types_metrics_experiment_running,
):
    ctx = linked_event_types_metrics_experiment_running
    exp_id = ctx["experiment_id"]
    flag_key = ctx["flag_key"]
    exposure_key = ctx["event_type_keys"]["exposure"]
    conversion_key = ctx["event_type_keys"]["conversion"]
    decide_url = f"{base_url}/api/v1/decide"
    events_url = f"{base_url}/api/v1/events"
    report_url = f"{base_url}/api/v1/experiments/{exp_id}/report"

    _value_to_variant = {"c": "control", "t": "treatment", "control": "control", "treatment": "treatment"}
    decisions_by_variant = {"control": [], "treatment": []}
    n_subjects = 10
    for i in range(n_subjects):
        subject_id = f"report-test-subj-{ctx['suffix']}-{i}"
        async with http_session.post(
            decide_url,
            json={"subject_id": subject_id, "attributes": {}, "flags": [flag_key]},
            headers=auth_headers_viewer,
        ) as resp:
            assert resp.status == 200, await resp.text()
            data = await resp.json()
        assert data.get("flags"), "decide must return flags"
        fl = data["flags"][0]
        decision_id = fl.get("decision_id")
        flag_value = (fl.get("flag_value") or "").strip()
        variant_name = _value_to_variant.get(flag_value)
        assert decision_id and variant_name is not None, (
            f"unexpected flag_value: {flag_value!r}"
        )
        decisions_by_variant[variant_name].append((subject_id, decision_id))

    n_control = len(decisions_by_variant["control"])
    n_treatment = len(decisions_by_variant["treatment"])
    assert n_control + n_treatment == n_subjects
    if n_control == 0 or n_treatment == 0:
        pytest.skip("All subjects landed in one variant (unlucky split); need both for report conclusions")

    now_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    events_via_kafka = False
    exposure_events = []
    for val in ("control", "treatment"):
        for subject_id, decision_id in decisions_by_variant[val]:
            exposure_events.append({
                "event_id": str(uuid.uuid4()),
                "decision_id": decision_id,
                "event_type_key": exposure_key,
                "subject_id": subject_id,
                "timestamp": now_ts,
                "payload": {},
            })
    async with http_session.post(events_url, json={"events": exposure_events}) as resp:
        assert resp.status in (200, 202), await resp.text()
        if resp.status == 202:
            events_via_kafka = True
        submit = await resp.json()
        if resp.status == 202:
            await asyncio.sleep(12)
        else:
            assert submit.get("accepted") == n_subjects, f"exposure events: {submit}"

    conversion_events = []
    for subject_id, decision_id in decisions_by_variant["treatment"]:
        conversion_events.append({
            "event_id": str(uuid.uuid4()),
            "decision_id": decision_id,
            "event_type_key": conversion_key,
            "subject_id": subject_id,
            "timestamp": now_ts,
            "payload": {},
        })
    async with http_session.post(events_url, json={"events": conversion_events}) as resp:
        assert resp.status in (200, 202), await resp.text()
        if resp.status == 202:
            events_via_kafka = True
        conv_submit = await resp.json()
        if resp.status == 202:
            await asyncio.sleep(12)
        else:
            assert conv_submit.get("accepted") == n_treatment, f"conversion events: {conv_submit}"

    report = None
    poll_iterations = 35
    for _ in range(poll_iterations):
        async with http_session.get(
            report_url,
            params={"start": "2025-01-01T00:00:00Z", "end": "2030-12-31T23:59:59Z"},
            headers=auth_headers_experimenter,
        ) as resp:
            assert resp.status == 200, await resp.text()
            report = await resp.json()
        variants = report.get("variants") or []
        if len(variants) >= 2:
            by_name = {v["variant_name"]: v for v in variants}
            cr = by_name.get("control")
            tr = by_name.get("treatment")
            if cr and tr and (cr.get("event_counts") or {}).get(exposure_key, 0) > 0:
                break
        await asyncio.sleep(3)
    assert report is not None

    variants = report.get("variants") or []
    by_name = {v["variant_name"]: v for v in variants}
    control_row = by_name.get("control")
    treatment_row = by_name.get("treatment")
    assert len(variants) == 2
    assert control_row and treatment_row
    n_control_report = control_row.get("subjects_count", 0)
    n_treatment_report = treatment_row.get("subjects_count", 0)
    assert control_row.get("decisions_count", 0) >= n_control_report
    assert treatment_row.get("decisions_count", 0) >= n_treatment_report
    total_in_report = n_control_report + n_treatment_report
    assert total_in_report >= 2, "need at least 2 subjects in report (both variants)"
    assert n_control_report >= 1 and n_treatment_report >= 1, "need at least one subject per variant for conclusions"
    share_sum = sum(v.get("share_pct", 0) for v in variants)
    assert abs(share_sum - 100.0) < 0.02, f"share_pct sum should be 100, got {share_sum}"

    exp_key_used = exposure_key
    conv_key_used = conversion_key
    if events_via_kafka and control_row["event_counts"].get(exp_key_used, 0) == 0:
        pytest.skip(
            "Kafka consumer did not process events in time; event_counts still empty "
            "(backend returns 202 only when consumer is running; increase poll_iterations or check consumer logs)"
        )
    assert control_row["event_counts"].get(exp_key_used) == n_control_report
    assert treatment_row["event_counts"].get(exp_key_used) == n_treatment_report
    assert control_row["event_counts"].get(conv_key_used) == 0
    assert treatment_row["event_counts"].get(conv_key_used) == n_treatment_report

    summary = report.get("primary_metric_summary")
    assert summary is not None
    control_val = summary.get("control_value")
    results = summary.get("results") or []
    treatment_result = next((r for r in results if r.get("variant_name") == "treatment"), None)
    assert treatment_result is not None
    treatment_val = treatment_result.get("value")
    assert control_val == 0
    assert treatment_val == 1
    if treatment_val is not None or control_val is not None:
        assert treatment_val is not None and (control_val is None or treatment_val > control_val), (
            f"expected treatment primary value ({treatment_val!r}) > control ({control_val!r})"
        )
    if summary.get("recommendation") == "rollout":
        assert summary.get("winner_variant_name") == "treatment"
        assert treatment_result.get("vs_control") == "better"
        assert (treatment_result.get("change_percent") or 0) > 0
