from marshmallow import Schema, fields, validate as mvalidate

class UserAuthSchema(Schema):
    identifier = fields.Str(required=True)
    password = fields.Str(required=True)


class AuthLoginSchema(Schema):
    email = fields.Str(required=True, description="Email пользователя")
    password = fields.Str(required=True, description="Пароль")


class AuthLoginResponseSchema(Schema):
    token = fields.Str(description="JWT для заголовка Authorization: Bearer <token>")
    user = fields.Dict(description="Данные пользователя без пароля")


class UserRegisterSchema(Schema):
    email = fields.Str(required=True, description="Email пользователя. До 256 символов")
    first_name = fields.Str(required=True, description="Имя пользователя")
    password = fields.Str(required=True, description="Пароль")


class UserCreateSchema(Schema):
    email = fields.Str(required=True, description="Email пользователя. До 256 символов")
    first_name = fields.Str(required=True, description="Имя пользователя")
    password = fields.Str(required=True, description="Пароль")
    role = fields.Str(
        load_default="viewer",
        validate=mvalidate.OneOf(("admin", "experimenter", "approver", "viewer")),
        description="Роль: admin, experimenter, approver, viewer",
    )


class UserProfileSchema(Schema):
    id = fields.Str(description="UUID пользователя")
    email = fields.Str()
    first_name = fields.Str()
    role = fields.Str()
    verified = fields.Bool(description="Верифицирован ли аккаунт")
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class UserEditSchema(Schema):
    email = fields.Str(required=False, description="Email пользователя. До 256 символов")
    first_name = fields.Str(required=False)
    password_old = fields.Str(required=False)
    password_new = fields.Str(required=False)


class UserUpdateSchema(Schema):
    email = fields.Str(required=False, description="Новый email")
    first_name = fields.Str(required=False, description="Новое имя")
    password = fields.Str(required=False, description="Новый пароль")
    role = fields.Str(
        required=False,
        validate=mvalidate.OneOf(("admin", "experimenter", "approver", "viewer")),
        description="Новая роль",
    )


class UserListQuerySchema(Schema):
    role = fields.Str(
        required=False,
        validate=mvalidate.OneOf(("admin", "experimenter", "approver", "viewer")),
        description="Фильтр по роли",
    )


class UserListResponseSchema(Schema):
    users = fields.List(fields.Nested(UserProfileSchema), description="Массив пользователей")


class ApproverGroupSetSchema(Schema):
    experimenter_id = fields.Str(required=False, allow_none=True, description="UUID экспериментатора или null")
    min_approvals = fields.Int(load_default=1, description="Минимум одобрений")
    approver_ids = fields.List(fields.Str(), load_default=list, description="UUID аппруверов")


class ApproverGroupUpdateSchema(Schema):
    min_approvals = fields.Int(required=False, description="Минимум одобрений")
    approver_ids = fields.List(fields.Str(), required=False, description="Новый список UUID аппруверов")


class ApproverGroupItemSchema(Schema):
    id = fields.Str()
    experimenter_id = fields.Str(allow_none=True)
    min_approvals = fields.Int()
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class ApproverGroupListResponseSchema(Schema):
    approver_groups = fields.List(fields.Nested(ApproverGroupItemSchema))


class FlagCreateSchema(Schema):
    key = fields.Str(required=True, description="Уникальный ключ флага (буква, цифры, подчёркивание)")
    value_type = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("string", "number", "bool")),
        description="Тип значения: string, number, bool",
    )
    default_value = fields.Str(required=True, description="Значение по умолчанию при отсутствии эксперимента")
    description = fields.Str(allow_none=True, description="Описание флага")
    owner = fields.Str(allow_none=True, description="Владелец/команда")
    metadata = fields.Dict(allow_none=True, description="Произвольные метаданные")


class FlagUpdateSchema(Schema):
    default_value = fields.Str(required=True, description="Новое значение по умолчанию (только это поле можно обновить)")


class ErrorDetailSchema(Schema):
    name = fields.Str(description="Имя параметра, вызвавшего ошибку")
    type = fields.Str(description="Тип ошибки (например, missing)")
    message = fields.Str(description="Сообщение об ошибке")
    value = fields.Raw(description="Значение параметра, если оно было передано", allow_none=True)


class Error400Schema(Schema):
    error = fields.Str(description="Общее сообщение об ошибке")
    errors = fields.List(fields.Nested(ErrorDetailSchema), description="Список детальных ошибок")
    received_params = fields.Dict(description="Параметры, которые были успешно получены")


class AlreadyBeenTaken(Schema):
    name = fields.Str(description="Название переменной, которая занята")
    error = fields.Str(description="Описание, что переменная занята")


AUTH_LOGIN_REQUEST_EXAMPLE = {
    "email": "admin@example.com",
    "password": "secret",
}

AUTH_LOGIN_RESPONSE_EXAMPLE = {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "email": "admin@example.com",
        "first_name": "Admin",
        "role": "admin",
        "verified": False,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    },
}

USER_CREATE_REQUEST_EXAMPLE = {
    "email": "viewer@example.com",
    "first_name": "Viewer",
    "password": "secure_password",
    "role": "viewer",
}

USER_UPDATE_REQUEST_EXAMPLE = {
    "email": "newemail@example.com",
    "first_name": "New Name",
    "password": "new_password",
    "role": "experimenter",
}

USER_LIST_QUERY_EXAMPLE = {"role": "viewer"}

APPROVER_GROUP_CREATE_REQUEST_EXAMPLE = {
    "experimenter_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "min_approvals": 2,
    "approver_ids": ["b2c3d4e5-f6a7-8901-bcde-f12345678901", "c3d4e5f6-a7b8-9012-cdef-123456789012"],
}

APPROVER_GROUP_UPDATE_REQUEST_EXAMPLE = {
    "min_approvals": 3,
    "approver_ids": ["b2c3d4e5-f6a7-8901-bcde-f12345678901"],
}