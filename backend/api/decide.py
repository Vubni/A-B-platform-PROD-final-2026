from typing import Any

from aiohttp import web
from aiohttp_apispec import docs, request_schema
from pydantic import BaseModel, field_validator

from api import validate
from api.system_metrics import record_decide
from docs.schems import RESPONSES_HTTP_ERROR, DecideRequestSchema, DecideResponseSchema
from functions.decide import get_decisions_for_subject
from functions.flags import get_flag_by_key


class DecideRequest(BaseModel):
    subject_id: str
    attributes: dict[str, Any] = {}
    flags: list[str]

    @field_validator("subject_id")
    @classmethod
    def subject_id_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("subject_id is required")
        v = v.strip()
        if len(v) > 1024:
            raise ValueError("subject_id must be at most 1024 characters")
        return v

    @field_validator("attributes", mode="before")
    @classmethod
    def attributes_default(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise ValueError("attributes must be an object")
        return {str(k): val for k, val in v.items()}

    @field_validator("flags")
    @classmethod
    def flags_validate(cls, v: list[str]) -> list[str]:
        if not v or len(v) == 0:
            raise ValueError("At least one flag is required")
        result = []
        for i, item in enumerate(v):
            if item is None or not isinstance(item, str) or not item.strip():
                raise ValueError(f"Flag key at index {i} must be a non-empty string")
            key = item.strip()
            if len(key) > 255:
                raise ValueError(f"Flag key at index {i} must be at most 255 characters")
            result.append(key)
        return result


@docs(
    tags=["Runtime Decide"],
    summary="Получить значения флагов для субъекта",
    responses={
        200: {
            "schema": DecideResponseSchema,
            "examples": {
                "application/json": {
                    "flags": [
                        {
                            "flag_key": "new_recommendations",
                            "flag_value": True,
                            "decision_id": "f7e6d5c4-b3a2-1098-7654-3210fedcba98",
                            "experiment": None,
                        },
                        {
                            "flag_key": "button_color",
                            "flag_value": "treatment_value",
                            "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "experiment": {
                                "experiment_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
                                "variant": "treatment",
                            },
                        },
                    ]
                }
            },
        },
        400: RESPONSES_HTTP_ERROR[400],
        401: RESPONSES_HTTP_ERROR[401],
        403: RESPONSES_HTTP_ERROR[403],
        404: RESPONSES_HTTP_ERROR[404],
        422: RESPONSES_HTTP_ERROR[422],
    },
)
@request_schema(DecideRequestSchema(), location="json", put_into="data")
@validate.validate(DecideRequest, require_auth=True)
async def decide(request: web.Request, parsed: DecideRequest) -> web.Response:
    record_decide()
    auth_payload = request["user_payload"]
    if not auth_payload:
        return validate.format_401_error(request)
    elif auth_payload["role"] != "viewer":
        return validate.format_403_error(request)

    for flag_key in parsed.flags:
        flag = await get_flag_by_key(flag_key)
        if not flag:
            return validate.format_404_error(request, f"Flag {flag_key!r} not found")

    result = await get_decisions_for_subject(parsed.subject_id, parsed.attributes, parsed.flags)
    return web.json_response(result, status=200)
