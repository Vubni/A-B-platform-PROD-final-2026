import os
import re
import uuid
from pathlib import Path

from aiohttp import web
from aiohttp_apispec import docs

from api import validate
from config import MAX_UPLOAD_BYTES, UPLOAD_DIR
from core import check_authorization, validate_uuid
from functions.attachments import (
    create_experiment_attachment,
    delete_experiment_attachment,
    get_experiment_attachment,
    list_experiment_attachments,
)
from functions.experiments import get_experiment_by_id

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
ALLOWED_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".pdf",
    ".png",
    ".txt",
    ".xlsx",
}


def _experiment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("id", "").strip()
    return validate_uuid(raw) if raw else None


def _attachment_id_from_request(request: web.Request) -> str | None:
    raw = request.match_info.get("attachment_id", "").strip()
    return validate_uuid(raw) if raw else None


def _safe_original_filename(filename: str) -> str:
    name = os.path.basename(filename or "").strip()
    if not name:
        return "attachment.bin"
    name = SAFE_NAME_RE.sub("_", name)
    return name[:255] or "attachment.bin"


def _stored_filename(original_filename: str) -> str:
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".bin"
    return f"{uuid.uuid4().hex}{ext}"


async def _load_experiment_for_attachment(request: web.Request):
    exp_id = _experiment_id_from_request(request)
    if not exp_id:
        return None, validate.format_404_error(request, "Invalid experiment id")
    experiment = await get_experiment_by_id(exp_id)
    if not experiment:
        return None, validate.format_404_error(request, "Experiment not found")
    return experiment, None


def _can_write_attachment(experiment: dict, auth_payload: dict) -> bool:
    role = auth_payload.get("role")
    if role == "admin":
        return True
    return role == "experimenter" and str(experiment.get("created_by")) == str(
        auth_payload.get("id")
    )


@docs(
    tags=["Experiment attachments"],
    summary="Список файлов эксперимента",
    responses={200: {"description": "Файлы эксперимента"}},
)
async def experiment_attachments_list(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    experiment, error = await _load_experiment_for_attachment(request)
    if error:
        return error
    attachments = await list_experiment_attachments(str(experiment["id"]))
    return web.json_response({"attachments": attachments})


@docs(
    tags=["Experiment attachments"],
    summary="Загрузить файл к эксперименту",
    responses={201: {"description": "Файл загружен"}},
)
async def experiment_attachment_upload(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    experiment, error = await _load_experiment_for_attachment(request)
    if error:
        return error
    if not _can_write_attachment(experiment, auth_payload):
        return validate.format_403_error(
            request, "Only owner experimenter or admin can upload files"
        )

    reader = await request.multipart()
    file_part = None
    description = None
    async for part in reader:
        if part.name == "description":
            description = (await part.text()).strip()[:2048] or None
        elif part.name == "file":
            file_part = part
            break
    if file_part is None or not file_part.filename:
        return validate.format_400_error(request, "multipart field 'file' is required")

    original_filename = _safe_original_filename(file_part.filename)
    stored_filename = _stored_filename(original_filename)
    target_dir = Path(UPLOAD_DIR).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / stored_filename

    size = 0
    with target_path.open("wb") as f:
        while True:
            chunk = await file_part.read_chunk()
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                target_path.unlink(missing_ok=True)
                return validate.format_400_error(
                    request,
                    "File is too large",
                    details={"max_bytes": MAX_UPLOAD_BYTES},
                )
            f.write(chunk)

    attachment = await create_experiment_attachment(
        experiment_id=str(experiment["id"]),
        uploaded_by=str(auth_payload.get("id")) if auth_payload.get("id") else None,
        original_filename=original_filename,
        stored_filename=stored_filename,
        content_type=file_part.headers.get("Content-Type", "application/octet-stream"),
        size_bytes=size,
        description=description,
    )
    if not attachment:
        target_path.unlink(missing_ok=True)
        return validate.format_500_error(request, "Failed to save attachment metadata")
    return web.json_response(attachment, status=201)


@docs(
    tags=["Experiment attachments"],
    summary="Скачать файл эксперимента",
    responses={200: {"description": "Файл"}},
)
async def experiment_attachment_download(request: web.Request) -> web.StreamResponse:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    experiment, error = await _load_experiment_for_attachment(request)
    if error:
        return error
    attachment_id = _attachment_id_from_request(request)
    if not attachment_id:
        return validate.format_404_error(request, "Invalid attachment id")
    attachment = await get_experiment_attachment(str(experiment["id"]), attachment_id)
    if not attachment:
        return validate.format_404_error(request, "Attachment not found")
    file_path = (Path(UPLOAD_DIR).resolve() / attachment["stored_filename"]).resolve()
    if not file_path.is_file():
        return validate.format_404_error(request, "Attachment file is missing on disk")
    return web.FileResponse(
        file_path,
        headers={
            "Content-Disposition": f'attachment; filename="{attachment["original_filename"]}"'
        },
    )


@docs(
    tags=["Experiment attachments"],
    summary="Удалить файл эксперимента",
    responses={204: {"description": "Файл удалён"}},
)
async def experiment_attachment_delete(request: web.Request) -> web.Response:
    auth_payload = await check_authorization(request)
    if not auth_payload:
        return validate.format_401_error(request, "Token is required")
    experiment, error = await _load_experiment_for_attachment(request)
    if error:
        return error
    if not _can_write_attachment(experiment, auth_payload):
        return validate.format_403_error(
            request, "Only owner experimenter or admin can delete files"
        )
    attachment_id = _attachment_id_from_request(request)
    if not attachment_id:
        return validate.format_404_error(request, "Invalid attachment id")
    attachment = await delete_experiment_attachment(str(experiment["id"]), attachment_id)
    if not attachment:
        return validate.format_404_error(request, "Attachment not found")
    file_path = (Path(UPLOAD_DIR).resolve() / attachment["stored_filename"]).resolve()
    file_path.unlink(missing_ok=True)
    return web.Response(status=204)
