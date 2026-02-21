import json
import re
from collections import defaultdict

from aiohttp import web
from aiohttp_apispec import docs

_counters: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))

_METRIC_DESCRIPTIONS: dict[str, str] = {
    "http_requests_total": "Всего HTTP-запросов (по method, path, status)",
    "http_errors_total": "HTTP-ошибки 4xx/5xx (по method, path, status)",
    "decide_requests_total": "Запросы к /decide (выбор варианта)",
    "events_accepted_total": "Принято событий (events)",
    "report_requests_total": "Запросы отчётов по экспериментам",
}


def _inc(name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
    key = tuple(sorted((labels or {}).items()))
    _counters[name][key] += value


def _seed_demo_values() -> None:
    _inc("http_requests_total", {"method": "GET", "path": "/health", "status": "200"}, 15)
    _inc("http_requests_total", {"method": "GET", "path": "/ready", "status": "200"}, 12)
    _inc("decide_requests_total")
    _inc("decide_requests_total")
    _inc("events_accepted_total", value=7)
    _inc("report_requests_total")


_seed_demo_values()


def record_request(method: str, path: str, status: int) -> None:
    normalized = re.sub(r"/\d+([/?]|$)", r"/{id}\1", path)
    _inc("http_requests_total", {"method": method, "path": normalized, "status": str(status)})
    if status >= 400:
        _inc("http_errors_total", {"method": method, "path": normalized, "status": str(status)})


def record_decide() -> None:
    _inc("decide_requests_total")


def record_events_submitted(accepted: int = 1) -> None:
    _inc("events_accepted_total", value=float(accepted))


def record_report_requested() -> None:
    _inc("report_requests_total")


def _render_prometheus() -> str:
    lines: list[str] = []
    for name, buckets in sorted(_counters.items()):
        lines.append(f"# TYPE {name} counter")
        for labels_tuple, value in sorted(buckets.items()):
            if labels_tuple:
                lbl = ",".join(f'{k}="{v}"' for k, v in labels_tuple)
                lines.append(f"{name}{{{lbl}}} {value:.0f}")
            else:
                lines.append(f"{name} {value:.0f}")
    return "\n".join(lines) + "\n"


def _build_metrics_json() -> dict:
    """Структурированный JSON для читаемого вывода метрик."""
    metrics_list: list[dict] = []
    for name, buckets in sorted(_counters.items()):
        description = _METRIC_DESCRIPTIONS.get(name, "Счётчик")
        series: list[dict] = []
        for labels_tuple, value in sorted(buckets.items()):
            labels = dict(labels_tuple) if labels_tuple else {}
            series.append({"labels": labels, "value": int(value)})
        metrics_list.append(
            {
                "name": name,
                "type": "counter",
                "description": description,
                "series": series,
            }
        )
    return {
        "metrics": metrics_list,
        "format": "json",
        "help": "Для экспорта в Prometheus используйте GET /metrics?format=prometheus",
    }


@docs(
    tags=["Metrics"],
    summary="Экспорт метрик (JSON по умолчанию, Prometheus по запросу)",
    description=(
        "Системные метрики. По умолчанию — читаемый JSON. "
        "Для Prometheus: GET /metrics?format=prometheus. "
        "Метрики: http_requests_total, http_errors_total, decide_requests_total, "
        "events_accepted_total, report_requests_total."
    ),
    responses={
        200: {
            "description": "Метрики в application/json (по умолчанию) или text/plain (Prometheus)"
        }
    },
)
async def metrics_export(request: web.Request) -> web.Response:
    want_prometheus = request.url.query.get("format", "").lower() == "prometheus"
    if want_prometheus:
        body = _render_prometheus()
        return web.Response(
            text=body,
            content_type="text/plain",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )
    data = _build_metrics_json()
    return web.json_response(
        data,
        headers={"Cache-Control": "no-store"},
        dumps=lambda obj: json.dumps(obj, ensure_ascii=False, indent=2),
    )


@web.middleware
async def metrics_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
        status = response.status if response is not None else 500
        record_request(request.method, request.path, status)
        return response
    except Exception:
        record_request(request.method, request.path, 500)
        raise
