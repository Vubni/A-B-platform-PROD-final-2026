from typing import Callable, Optional, TypeVar, Awaitable, Dict, Any, Union
from functools import wraps
from pydantic import BaseModel, ValidationError, Field
import json
from aiohttp import web
from pydantic import field_validator, model_validator
import core
import uuid
import re
import pytz
from datetime import datetime, timezone, timedelta

T = TypeVar("T", bound=BaseModel)


class EmailError(Exception):
    def __init__(self, message="Ошибка проверки email", errors=None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def get_nested_value(data: Dict[str, Any], path: tuple) -> Any:
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
    details: Optional[Dict[str, Any]] = None,
    field_errors: Optional[list] = None
) -> Dict[str, Any]:
    response = {
        "code": code,
        "message": message,
        "traceId": generate_trace_id(),
        "timestamp": get_timestamp(),
        "path": path
    }

    if details:
        response["details"] = details

    if field_errors:
        response["fieldErrors"] = field_errors

    return response


def format_401_error(request: web.Request, message: str = "Токен отсутствует, невалиден или истёк") -> web.Response:
    error_response = format_error_response(
        code="UNAUTHORIZED",
        message=message,
        path=str(request.path_qs),
        status=401
    )
    return web.json_response(error_response, status=401)


def format_403_error(request: web.Request, message: str = "Недостаточно прав для выполнения операции") -> web.Response:
    error_response = format_error_response(
        code="FORBIDDEN",
        message=message,
        path=str(request.path_qs),
        status=403
    )
    return web.json_response(error_response, status=403)


def format_404_error(request: web.Request, message: str = "Ресурс не найден", details: Optional[Dict[str, Any]] = None) -> web.Response:
    error_response = format_error_response(
        code="NOT_FOUND",
        message=message,
        path=str(request.path_qs),
        status=404,
        details=details
    )
    return web.json_response(error_response, status=404)


def format_409_error(request: web.Request, value, message: str = "Токен отсутствует или невалиден", field="email") -> web.Response:
    error_response = format_error_response(
        code=f"{field.upper()}_ALREADY_EXISTS",
        message=message,
        path=str(request.path_qs),
        status=409,
        details={"field": field, "value": value}
    )
    return web.json_response(error_response, status=409)


def format_422_error(request: web.Request, code: str = "ERROR") -> web.Response:
    error_response = {
        "code": code,
        "message": "Некоторые поля не прошли валидацию",
        "timestamp": get_timestamp(),
        "path": str(request.path_qs)
    }
    return web.json_response(error_response, status=422)


def format_423_error(request: web.Request, message: str = "Пользователь деактивирован") -> web.Response:
    error_response = {
        "code": "USER_INACTIVE",
        "message": message,
        "timestamp": get_timestamp(),
        "path": str(request.path_qs)
    }
    return web.json_response(error_response, status=423)


def require_auth(handler: Callable[[web.Request, Any], Awaitable[web.Response]]) -> Callable:
    @wraps(handler)
    async def wrapper(request: web.Request, *args, **kwargs) -> web.Response:
        payload = await core.check_authorization(request)
        if not isinstance(payload, dict):
            if payload is not None and isinstance(payload, web.Response):
                return payload
            return format_401_error(request)
        request['user_payload'] = payload
        return await handler(request, *args, **kwargs)
    return wrapper


def validate(model: type[T], require_auth: bool = False) -> Callable:
    def decorator(handler: Callable[[web.Request, Any], Awaitable[web.Response]]):
        @wraps(handler)
        async def wrapper(request: web.Request) -> web.Response:
            path = str(request.path_qs)

            if require_auth:
                payload = await core.check_authorization(request)
                if not isinstance(payload, dict):
                    if payload is not None and isinstance(payload, web.Response):
                        return payload
                    return format_401_error(request)
                request["user_payload"] = payload

            if request.method in ('POST', 'PUT', 'PATCH'):
                content_type = request.headers.get('Content-Type', '')
                if not content_type.startswith('application/json'):
                    error_response = format_error_response(
                        code="BAD_REQUEST",
                        message="Неподдерживаемый Content-Type",
                        path=path,
                        status=400,
                        details={
                            "hint": "Используйте Content-Type: application/json"}
                    )
                    return web.json_response(error_response, status=400)

            if request.method == 'GET':
                data = dict(request.query)
            else:
                content_length = request.headers.get('Content-Length')
                if content_length:
                    try:
                        size = int(content_length)
                        if size > 10 * 1024 * 1024:
                            error_response = format_error_response(
                                code="BAD_REQUEST",
                                message="Слишком большой payload",
                                path=path,
                                status=400,
                                details={
                                    "hint": "Максимальный размер запроса: 10MB"}
                            )
                            return web.json_response(error_response, status=400)
                    except ValueError:
                        pass

                try:
                    data = await request.json()
                except json.JSONDecodeError as e:
                    error_response = format_error_response(
                        code="BAD_REQUEST",
                        message="Невалидный JSON",
                        path=path,
                        status=400,
                        details={"hint": "Проверьте запятые/кавычки"}
                    )
                    return web.json_response(error_response, status=400)
                except Exception:
                    error_response = format_error_response(
                        code="BAD_REQUEST",
                        message="Ошибка обработки запроса",
                        path=path,
                        status=400,
                        details={"hint": "Проверьте формат и размер запроса"}
                    )
                    return web.json_response(error_response, status=400)

            all_data = dict(request.query)
            all_data.update(data)

            for key, value in all_data.items():
                if isinstance(value, str):
                    if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                        try:
                            all_data[key] = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif '.' in value:
                        try:
                            all_data[key] = float(value)
                        except (ValueError, TypeError):
                            pass
                    elif value.lower() == 'true':
                        all_data[key] = True
                    elif value.lower() == 'false':
                        all_data[key] = False

            try:
                parsed = model(**all_data)
            except ValidationError as e:
                field_errors = [
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]) if error["loc"] else "general",
                        "issue": error["msg"],
                        "rejectedValue": get_nested_value(all_data, tuple(error["loc"])) if error["loc"] else None
                    }
                    for error in e.errors()
                ]
                error_response = format_error_response(
                    code="VALIDATION_FAILED",
                    message="Некоторые поля не прошли валидацию",
                    path=path,
                    status=422,
                    field_errors=field_errors
                )
                return web.json_response(error_response, status=422)
            except EmailError as e:
                field_errors = [
                    {
                        "field": "email",
                        "issue": e.message,
                        "rejectedValue": all_data.get("email")
                    }
                ]
                error_response = format_error_response(
                    code="VALIDATION_FAILED",
                    message="Некоторые поля не прошли валидацию",
                    path=path,
                    status=422,
                    field_errors=field_errors
                )
                return web.json_response(error_response, status=422)

            return await handler(request, parsed)
        return wrapper
    return decorator


class Register(BaseModel):
    email: str
    fullName: str
    password: str
    region: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    maritalStatus: Optional[str] = None

    @field_validator('email')
    def check_email(cls, v):
        if len(v) > 254:
            raise ValueError('Email cannot exceed 254 characters')
        if not core.is_valid_email(v):
            raise EmailError(
                'Email does not comply with email standards or dns mail servers are not found')
        return v

    @field_validator('age')
    def check_age(cls, v):
        if v is not None and (v < 18 or v > 120):
            raise ValueError('Age must be between 18 and 120')
        return v

    @field_validator('fullName')
    def check_full_name(cls, v):
        if v is not None and (len(v) < 2 or len(v) > 100):
            raise ValueError('Full name must be between 2 and 100 characters')
        return v

    @field_validator('password')
    def check_password(cls, v):
        if v is not None:
            if (len(v) < 8 or len(v) > 72):
                raise ValueError(
                    'Password must be between 8 and 72 characters')
            if re.match(r'^(?=.*[A-Za-z])(?=.*\d).+$', v) is None:
                raise ValueError(
                    'Password must contain at least one letter and one number')
        return v

    @field_validator('region')
    def check_region(cls, v):
        if v is not None and len(v) > 32:
            raise ValueError('Region cannot exceed 32 characters')
        return v

    @field_validator('gender')
    def check_gender(cls, v):
        if v not in ['MALE', 'FEMALE', None]:
            raise ValueError('Gender must be either MALE or FEMALE')
        return v

    @field_validator('maritalStatus')
    def check_marital_status(cls, v):
        if v not in ['SINGLE', 'MARRIED', 'DIVORCED', 'WIDOWED', None]:
            raise ValueError(
                'Marital status must be either SINGLE or MARRIED or DIVORCED or WIDOWED')
        return v
