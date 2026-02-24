import json
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from typing import Any

from aiohttp import web
from pydantic import BaseModel, ValidationError, field_validator

import core


class EmailError(Exception):
    def __init__(self, message="Ошибка проверки email", errors=None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def get_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def get_nested_value(data: dict[str, Any], path: tuple) -> Any:
    if not path:
        return None

    current = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return None
        else:
            return None

    return current


def format_error_response(
    code: str,
    message: str,
    path: str,
    status: int,
    details: dict[str, Any] | None = None,
    field_errors: list | None = None,
) -> dict[str, Any]:
    response = {
        "code": code,
        "message": message,
        "traceId": generate_trace_id(),
        "timestamp": get_timestamp(),
        "path": path,
    }
    if details:
        response["details"] = details
    if field_errors:
        response["fieldErrors"] = field_errors
    return response


def format_http_error(
    request: web.Request,
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    field_errors: list | None = None,
) -> web.Response:
    body = format_error_response(
        code=code,
        message=message,
        path=str(request.path_qs),
        status=status,
        details=details,
        field_errors=field_errors,
    )
    return web.json_response(body, status=status)


def format_400_error(
    request: web.Request,
    message: str = "Некорректный запрос",
    details: dict[str, Any] | None = None,
) -> web.Response:
    return format_http_error(request, 400, "BAD_REQUEST", message, details=details)


def format_401_error(
    request: web.Request, message: str = "Токен отсутствует, невалиден или истёк"
) -> web.Response:
    return format_http_error(request, 401, "UNAUTHORIZED", message)


def format_403_error(
    request: web.Request, message: str = "Недостаточно прав для выполнения операции"
) -> web.Response:
    return format_http_error(request, 403, "FORBIDDEN", message)


def format_404_error(
    request: web.Request,
    message: str = "Ресурс не найден",
    details: dict[str, Any] | None = None,
) -> web.Response:
    return format_http_error(request, 404, "NOT_FOUND", message, details=details)


def format_409_error(
    request: web.Request, value, message: str = "Токен отсутствует или невалиден", field="email"
) -> web.Response:
    return format_http_error(
        request,
        409,
        f"{field.upper()}_ALREADY_EXISTS",
        message,
        details={"field": field, "value": value},
    )


def format_409_conflict(
    request: web.Request, message: str, code: str = "CONFLICT"
) -> web.Response:
    return format_http_error(request, 409, code, message)


def format_422_error(
    request: web.Request,
    code: str = "VALIDATION_FAILED",
    message: str = "Некоторые поля не прошли валидацию",
    field_errors: list | None = None,
) -> web.Response:
    return format_http_error(request, 422, code, message, field_errors=field_errors)


def format_423_error(
    request: web.Request, message: str = "Пользователь деактивирован"
) -> web.Response:
    return format_http_error(request, 423, "USER_INACTIVE", message)


def format_500_error(
    request: web.Request,
    message: str = "Внутренняя ошибка сервера",
    details: dict[str, Any] | None = None,
) -> web.Response:
    return format_http_error(request, 500, "INTERNAL_ERROR", message, details=details)


def require_auth(handler: Callable[[web.Request, Any], Awaitable[web.Response]]) -> Callable:
    @wraps(handler)
    async def wrapper(request: web.Request, *args, **kwargs) -> web.Response:
        payload = await core.check_authorization(request)
        if not isinstance(payload, dict):
            if payload is not None and isinstance(payload, web.Response):
                return payload
            return format_401_error(request)
        request["user_payload"] = payload
        return await handler(request, *args, **kwargs)

    return wrapper


def validate[T: BaseModel](model: type[T], require_auth: bool = False) -> Callable:
    def decorator(handler: Callable[[web.Request, Any], Awaitable[web.Response]]):
        @wraps(handler)
        async def wrapper(request: web.Request) -> web.Response:
            if require_auth:
                payload = await core.check_authorization(request)
                if not isinstance(payload, dict):
                    if payload is not None and isinstance(payload, web.Response):
                        return payload
                    return format_401_error(request)
                request["user_payload"] = payload

            if request.method in ("POST", "PUT", "PATCH"):
                content_type = request.headers.get("Content-Type", "")
                if not content_type.startswith("application/json"):
                    return format_400_error(
                        request,
                        "Неподдерживаемый Content-Type",
                        details={"hint": "Используйте Content-Type: application/json"},
                    )

            if request.method == "GET":
                data = dict(request.query)
            else:
                content_length = request.headers.get("Content-Length")
                if content_length:
                    try:
                        size = int(content_length)
                        if size > 10 * 1024 * 1024:
                            return format_400_error(
                                request,
                                "Слишком большой payload",
                                details={"hint": "Максимальный размер запроса: 10MB"},
                            )
                    except ValueError:
                        pass

                try:
                    data = await request.json()
                except json.JSONDecodeError:
                    return format_400_error(
                        request,
                        "Невалидный JSON",
                        details={"hint": "Проверьте запятые/кавычки"},
                    )
                except Exception:
                    return format_400_error(
                        request,
                        "Ошибка обработки запроса",
                        details={"hint": "Проверьте формат и размер запроса"},
                    )

            all_data = dict(request.query)
            all_data.update(data)

            for key, value in all_data.items():
                if isinstance(value, str):
                    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                        try:
                            all_data[key] = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif "." in value:
                        try:
                            all_data[key] = float(value)
                        except (ValueError, TypeError):
                            pass
                    elif value.lower() == "true":
                        all_data[key] = True
                    elif value.lower() == "false":
                        all_data[key] = False

            try:
                parsed = model(**all_data)
            except ValidationError as e:
                field_errors = [
                    {
                        "field": ".".join(str(loc) for loc in error["loc"])
                        if error["loc"]
                        else "general",
                        "issue": error["msg"],
                        "rejectedValue": get_nested_value(all_data, tuple(error["loc"]))
                        if error["loc"]
                        else None,
                    }
                    for error in e.errors()
                ]
                return format_422_error(
                    request,
                    code="VALIDATION_FAILED",
                    message="Некоторые поля не прошли валидацию",
                    field_errors=field_errors,
                )
            except EmailError as e:
                field_errors = [
                    {"field": "email", "issue": e.message, "rejectedValue": all_data.get("email")}
                ]
                return format_422_error(
                    request,
                    code="VALIDATION_FAILED",
                    message="Некоторые поля не прошли валидацию",
                    field_errors=field_errors,
                )

            return await handler(request, parsed)

        return wrapper

    return decorator


class Register(BaseModel):
    email: str
    fullName: str
    password: str
    region: str | None = None
    gender: str | None = None
    age: int | None = None
    maritalStatus: str | None = None

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        v = v.strip() if isinstance(v, str) else v
        if not v:
            raise ValueError("Email is required")
        if len(v) > 254:
            raise ValueError("Email cannot exceed 254 characters")
        if not core.is_valid_email(v):
            raise EmailError(
                "Email does not comply with email standards or dns mail servers are not found"
            )
        return v

    @field_validator("age")
    @classmethod
    def check_age(cls, v):
        if v is not None and (v < 18 or v > 120):
            raise ValueError("Age must be between 18 and 120")
        return v

    @field_validator("fullName")
    @classmethod
    def check_full_name(cls, v):
        if v is not None and (len(v) < 2 or len(v) > 100):
            raise ValueError("Full name must be between 2 and 100 characters")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v):
        if v is not None:
            if len(v) < 8 or len(v) > 72:
                raise ValueError("Password must be between 8 and 72 characters")
            if re.match(r"^(?=.*[A-Za-z])(?=.*\d).+$", v) is None:
                raise ValueError("Password must contain at least one letter and one number")
        return v

    @field_validator("region")
    @classmethod
    def check_region(cls, v):
        if v is not None and len(v) > 32:
            raise ValueError("Region cannot exceed 32 characters")
        return v

    @field_validator("gender")
    @classmethod
    def check_gender(cls, v):
        if v not in ["MALE", "FEMALE", None]:
            raise ValueError("Gender must be either MALE or FEMALE")
        return v

    @field_validator("maritalStatus")
    @classmethod
    def check_marital_status(cls, v):
        if v not in ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED", None]:
            raise ValueError(
                "Marital status must be either SINGLE or MARRIED or DIVORCED or WIDOWED"
            )
        return v
