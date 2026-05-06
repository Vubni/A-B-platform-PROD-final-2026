import time
import re

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from config import AUTH_TOKEN_EXPIRATION
from core import check_token, create_token, is_valid_email
from docs.schems import (
    RESPONSES_HTTP_ERROR,
    AuthLoginResponseSchema,
    AuthLoginSchema,
    UserRegisterSchema,
)
from functions.users import create_user, get_user_by_email


class AuthLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_non_empty(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("email is required")
        v = v.strip()
        if len(v) > 254:
            raise ValueError("email cannot exceed 254 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_non_empty(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("password is required")
        return v


class UserRegister(BaseModel):
    email: str
    first_name: str
    password: str

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("email is required")
        v = v.strip()
        if len(v) > 254:
            raise ValueError("email cannot exceed 254 characters")
        if not is_valid_email(v):
            raise ValueError("email must be a valid email address")
        return v

    @field_validator("first_name")
    @classmethod
    def first_name_valid(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("first_name is required")
        v = v.strip()
        if len(v) > 255:
            raise ValueError("first_name must be at most 255 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("password is required")
        if len(v) < 8 or len(v) > 72:
            raise ValueError("password must be between 8 and 72 characters")
        if re.match(r"^(?=.*[A-Za-z])(?=.*\d).+$", v) is None:
            raise ValueError("password must contain at least one letter and one number")
        return v


def _issue_auth_response(user: dict) -> web.Response:
    token_payload = {
        "id": user["id"],
        "role": user["role"],
        "exp": int(time.time()) + AUTH_TOKEN_EXPIRATION,
    }
    token = create_token(token_payload)
    return web.json_response(
        {
            "token": token,
            "user": user,
        }
    )


@docs(
    tags=["Auth"],
    summary="Регистрация",
    responses={
        201: {"schema": AuthLoginResponseSchema},
        400: RESPONSES_HTTP_ERROR[400],
        409: RESPONSES_HTTP_ERROR[409],
        422: RESPONSES_HTTP_ERROR[422],
    },
)
@request_schema(UserRegisterSchema(), location="json", put_into="data")
@validate.validate(UserRegister)
async def auth_register(request: web.Request, parsed: UserRegister) -> web.Response:
    user = await create_user(
        email=parsed.email,
        first_name=parsed.first_name,
        password=parsed.password,
        role="viewer",
    )
    if not user:
        return validate.format_409_error(
            request, "User with such email or first_name already exists"
        )
    response = _issue_auth_response(user)
    response.set_status(201)
    return response


@docs(
    tags=["Auth"],
    summary="Авторизация",
    responses={
        200: {"schema": AuthLoginResponseSchema},
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        422: RESPONSES_HTTP_ERROR[422],
    },
)
@request_schema(AuthLoginSchema(), location="json", put_into="data")
@validate.validate(AuthLogin)
async def auth_login(request: web.Request, parsed: AuthLogin) -> web.Response:
    user = await get_user_by_email(parsed.email)
    if not user:
        return validate.format_401_error(request, "Invalid email or password")

    stored_password = user.pop("password", None)
    if not stored_password:
        return validate.format_401_error(request, "Invalid email or password")
    decoded = check_token(stored_password)
    if not decoded or decoded.get("password") != parsed.password:
        return validate.format_401_error(request, "Invalid email or password")

    return _issue_auth_response(user)
