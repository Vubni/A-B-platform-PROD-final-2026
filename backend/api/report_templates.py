from datetime import datetime
from pathlib import Path

from aiohttp import web
from aiohttp_apispec import docs
from jinja2 import Environment, FileSystemLoader, select_autoescape

from api import validate
from api.system_metrics import record_report_requested
from core import check_authorization, validate_uuid
from functions.experiments import get_experiment_by_id
from functions.reports import get_experiment_report

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(("html", "xml")),
)


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    return validate_uuid(raw) if raw else None


def _is_valid_window(start: str | None, end: str | None) -> bool:
    if not start or not end:
        return False
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return start_dt < end_dt


@docs(
    tags=["Reports"],
    summary="HTML-отчёт по эксперименту через Jinja2-шаблон",
    responses={200: {"description": "HTML отчёт"}},
)
async def reports_experiment_html(request: web.Request) -> web.Response:
    record_report_requested()
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")

    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return validate.format_404_error(request, "Invalid experiment id")
    start = request.query.get("start")
    end = request.query.get("end")
    if not _is_valid_window(start, end):
        return validate.format_400_error(request, "start/end must be a valid ISO 8601 window")

    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return validate.format_404_error(request, "Experiment not found")

    report = await get_experiment_report(experiment, start, end)
    template = _jinja_env.get_template("experiment_report.html")
    html = template.render(report=report, experiment=experiment)
    return web.Response(text=html, content_type="text/html")
