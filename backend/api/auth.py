import time

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from config import AUTH_TOKEN_EXPIRATION
from core import check_token, create_token
from docs.schems import RESPONSES_HTTP_ERROR, AuthLoginResponseSchema, AuthLoginSchema
from functions.users import get_user_by_email


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


@docs(
    tags=["Auth"],
    summary="Авторизация",
    description=("Авторизация, возвращает токен и данные пользователя"),
    responses={
        200: {
            "description": "Успешный вход (token, user без пароля)",
            "schema": AuthLoginResponseSchema,
        },
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
