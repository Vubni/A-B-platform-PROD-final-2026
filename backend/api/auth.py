import json
import time

from aiohttp import web
from aiohttp_apispec import docs, request_schema

from docs.schems import AuthLoginSchema
from pydantic import BaseModel

from core import check_token, create_token
from functions.users import get_user_by_email
from api import validate
from config import AUTH_TOKEN_EXPIRATION

class AuthLogin(BaseModel):
    email: str
    password: str


@docs(
    tags=["Auth"],
    summary="Авторизация (логин)",
    description=(
        "Принять email и пароль, вернуть JWT-токен сессии и данные пользователя (без пароля). "
        "Токен передавать в заголовке: Authorization: Bearer <token>."
    ),
    responses={
        200: {"description": "Успешный вход (token, user)"},
        400: {"description": "Некорректный запрос"},
        401: {"description": "Неверный email или пароль"},
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
        "user_id": user["id"],
        "role": user["role"],
        "exp": int(time.time()) + AUTH_TOKEN_EXPIRATION,
    }
    token = create_token(token_payload)

    return web.json_response({
        "token": token,
        "user": user,
    })
