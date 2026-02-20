import asyncio
import re
import secrets
import string
import threading
import time
import uuid
from datetime import UTC, date, datetime
from datetime import time as time_type
from decimal import Decimal
from functools import wraps
from typing import Any

import jwt
from aiohttp import web

from config import SECRET, logger

FLAG_KEY_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


async def check_authorization(request: web.Request):
    try:
        auth_header = request.headers.get("Authorization")

        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                result = check_token(parts[1])
                return result
        return None
    except Exception as e:
        logger.error("check_authorization error: ", e)
        return None


def validate_uuid(v: str) -> str:
    try:
        return str(uuid.UUID(v))
    except (ValueError, TypeError):
        return None


def create_token(payload) -> str:
    token = jwt.encode(payload, SECRET, algorithm="HS256")

    return token


def parse_uuid(value: str) -> str | None:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError):
        return None


def check_token(token):
    try:
        decoded = jwt.decode(token, SECRET, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_unique_code(length: int = 32):
    characters = string.ascii_letters + string.digits + "_"
    return "".join(secrets.choice(characters) for _ in range(length))


def is_domain_valid(domain):
    segments = domain.split(".")
    for segment in segments:
        if not segment:
            return False
        if segment[0] == "-" or segment[-1] == "-":
            return False
        if not re.match(r"^[a-zA-Z0-9-]+$", segment):
            return False
    return True


def is_valid_email(email: str) -> bool:
    regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(regex, email):
        return False

    local_part, domain_part = email.split("@")

    if len(local_part) > 64:
        return False
    if local_part.startswith(".") or local_part.endswith("."):
        return False
    if ".." in local_part:
        return False

    if not is_domain_valid(domain_part):
        return False
    if len(domain_part) > 255:
        return False

    return True


def parse_iso_timestamp(value: Any) -> tuple[datetime | None, str | None]:
    if value is None:
        return None, "timestamp is required"
    if isinstance(value, datetime):
        return value, None
    s = str(value).strip()
    if not s:
        return None, "timestamp is required"
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt, None
    except (ValueError, TypeError):
        return None, f"invalid timestamp: {s!r}"


def serialize_json(obj):
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    elif hasattr(obj, "dict"):
        obj = obj.dict()

    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            return obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            return obj.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif isinstance(obj, date) and not isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%dT00:00:00Z")
    elif isinstance(obj, time_type):
        return datetime.combine(date(1970, 1, 1), obj).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif isinstance(obj, dict):
        return {key: serialize_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        result = [serialize_json(item) for item in obj]
        return tuple(result) if isinstance(obj, tuple) else result
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


def is_hashable(obj):
    try:
        hash(obj)
        return True
    except TypeError:
        return False


def cache_with_expiration(expiration_seconds: int):
    def decorator(func):
        cache = {}
        async_lock = None
        sync_lock = threading.Lock()

        def get_cache_key(*args, **kwargs):
            filtered_args = [arg for arg in args if is_hashable(arg)]
            filtered_kwargs = {k: v for k, v in kwargs.items() if is_hashable(v)}
            return (tuple(filtered_args), frozenset(filtered_kwargs.items()))

        @wraps(func)
        async def async_wrapped(*args, **kwargs):
            nonlocal async_lock
            if async_lock is None:
                async_lock = asyncio.Lock()
            async with async_lock:
                now = time.time()
                key = get_cache_key(*args, **kwargs)
                if key in cache:
                    result, timestamp = cache[key]
                    if now - timestamp < expiration_seconds:
                        return result
                result = await func(*args, **kwargs)
                cache[key] = (result, now)
                return result

        @wraps(func)
        def sync_wrapped(*args, **kwargs):
            with sync_lock:
                now = time.time()
                key = get_cache_key(*args, **kwargs)
                if key in cache:
                    result, timestamp = cache[key]
                    if now - timestamp < expiration_seconds:
                        return result
                result = func(*args, **kwargs)
                cache[key] = (result, now)
                return result

        return async_wrapped if asyncio.iscoroutinefunction(func) else sync_wrapped

    return decorator
