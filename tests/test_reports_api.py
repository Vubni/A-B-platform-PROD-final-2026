"""
Тесты API отчётов по эксперименту (GET /api/v1/experiments/{id}/report).
Отчёты строятся по метрикам эксперимента, метрики привязаны к типам событий — тесты используют связанную цепочку (linked_event_types_metrics_experiment).
"""
import pytest


@pytest.mark.asyncio
async def test_report_requires_auth(http_session, base_url):
    """GET report без токена возвращает 401."""
    url = f"{base_url}/api/v1/experiments/00000000-0000-0000-0000-000000000001/report"
    async with http_session.get(url, params={"start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z"}) as resp:
        assert resp.status == 401
        data = await resp.json()
        assert data.get("code") == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_report_experiment_not_found(
    http_session, base_url, auth_headers_experimenter
):
    """GET report по несуществующему эксперименту возвращает 404."""
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
    """GET report без start или end возвращает 400/422."""
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
    """GET report с невалидным окном (start >= end или не ISO) возвращает 400."""
    ctx = linked_event_types_metrics_experiment
    url = f"{base_url}/api/v1/experiments/{ctx['experiment_id']}/report"
    async with http_session.get(
        url,
        params={"start": "2026-02-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
        headers=auth_headers_experimenter,
    ) as resp:
        assert resp.status in (400, 422)


@pytest.mark.asyncio
async def test_report_success_structure(
    http_session, base_url, auth_headers_experimenter, linked_event_types_metrics_experiment
):
    """GET report возвращает 200 и ожидаемую структуру: experiment_id, context, metrics, variants, event_counts по типам событий."""
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
        assert "completion" in data
        assert "context" in data
        assert data["context"]["window_start"] == params["start"]
        assert data["context"]["window_end"] == params["end"]
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
            assert "metric_values" in v
            assert "event_counts" in v
            assert isinstance(v["event_counts"], dict)
            for slug in ("exposure", "conversion"):
                assert ctx["event_type_keys"][slug] in v["event_counts"]
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
    """В отчёте есть primary_metric_summary с control_value, results, summary_lines."""
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
    """У каждого варианта в отчёте metric_values соответствуют метрикам эксперимента (ключ, value, unit)."""
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
    """Viewer может запросить отчёт по эксперименту."""
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
