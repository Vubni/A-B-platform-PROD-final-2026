import re
from collections import defaultdict

from aiohttp import web
from aiohttp_apispec import docs

_counters: dict[str, dict[tuple, float]] = defaultdict(lambda: defaultdict(float))

_METRIC_DESCRIPTIONS: dict[str, str] = {
    "http_requests_total": "Total HTTP requests by method, path, status",
    "http_errors_total": "HTTP 4xx/5xx errors by method, path, status",
    "decide_requests_total": "Requests to /decide (variant selection)",
    "events_accepted_total": "Accepted events count",
    "report_requests_total": "Experiment report requests",
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
        help_desc = _METRIC_DESCRIPTIONS.get(name, "Counter")
        lines.append(f"# HELP {name} {help_desc}")
        lines.append(f"# TYPE {name} counter")
        for labels_tuple, value in sorted(buckets.items()):
            if labels_tuple:
                lbl = ",".join(f'{k}="{v}"' for k, v in labels_tuple)
                lines.append(f"{name}{{{lbl}}} {value:.0f}")
            else:
                lines.append(f"{name} {value:.0f}")
    return "\n".join(lines) + "\n"


@docs(
    tags=["Metrics"],
    summary="Экспорт метрик Prometheus",
    responses={200: {}},
)
async def metrics_export(request: web.Request) -> web.Response:
    body = _render_prometheus()
    return web.Response(
        text=body,
        content_type="text/plain",
        charset="utf-8",
        headers={"Cache-Control": "no-store"},
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
