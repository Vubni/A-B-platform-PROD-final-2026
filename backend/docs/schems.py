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

class ExperimentCreateSchema(Schema):
    flag_id = fields.Str(required=True, description="UUID флага")
    name = fields.Str(required=True, description="Название эксперимента, до 255 символов")
    audience_fraction = fields.Float(required=True, description="Доля аудитории в (0, 1]")
    targeting_rule = fields.Str(allow_none=True, description="Правило таргетинга, опционально")
    primary_metric_key = fields.Str(allow_none=True, description="Ключ основной метрики, опционально")


class ExperimentUpdateSchema(Schema):
    name = fields.Str(required=False, description="Новое название")
    audience_fraction = fields.Float(required=False, description="Новая доля аудитории (0, 1]")
    targeting_rule = fields.Str(required=False, allow_none=True)
    primary_metric_key = fields.Str(required=False, allow_none=True)


class StatusUpdateSchema(Schema):
    status = fields.Str(
        required=True,
        validate=mvalidate.OneOf((
            "draft", "on_review", "approved", "running", "paused",
            "completed", "archived", "rejected",
        )),
        description="Новый статус",
    )
    comment = fields.Str(allow_none=True, description="Комментарий (для ревью)")


class VariantCreateSchema(Schema):
    variant_name = fields.Str(required=True, description="Имя варианта")
    variant_value = fields.Str(required=True, description="Значение варианта")
    weight = fields.Float(required=True, description="Вес варианта (>= 0)")
    is_control = fields.Bool(load_default=False, description="Является ли контрольным")


class VariantUpdateSchema(Schema):
    variant_value = fields.Str(required=False, description="Новое значение")
    weight = fields.Float(required=False, description="Новый вес")
    is_control = fields.Bool(required=False, description="Является ли контрольным")


class ExperimentVariantSchema(Schema):
    id = fields.Str(description="UUID варианта")
    variant_name = fields.Str()
    variant_value = fields.Str()
    weight = fields.Float()
    is_control = fields.Bool()
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class ExperimentItemSchema(Schema):
    id = fields.Str()
    flag_id = fields.Str()
    flag_key = fields.Str(allow_none=True)
    name = fields.Str()
    status = fields.Str()
    audience_fraction = fields.Float()
    targeting_rule = fields.Str(allow_none=True)
    primary_metric_key = fields.Str(allow_none=True)
    version = fields.Int(allow_none=True)
    created_by = fields.Str(allow_none=True)
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)
    variants = fields.List(fields.Nested(ExperimentVariantSchema), allow_none=True)
    metrics = fields.List(fields.Dict(), allow_none=True)


class ExperimentListResponseSchema(Schema):
    experiments = fields.List(fields.Nested(ExperimentItemSchema), description="Массив экспериментов")


class GuardrailHistoryResponseSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    triggers = fields.List(fields.Dict(), description="История срабатываний guardrail")


class FlagItemSchema(Schema):
    id = fields.Str()
    key = fields.Str()
    value_type = fields.Str()
    default_value = fields.Str()
    description = fields.Str(allow_none=True)
    owner = fields.Str(allow_none=True)
    metadata = fields.Dict(allow_none=True)
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class FlagListResponseSchema(Schema):
    flags = fields.List(fields.Nested(FlagItemSchema), description="Массив флагов")


class DecideRequestSchema(Schema):
    subject_id = fields.Str(required=True, description="Идентификатор субъекта")
    attributes = fields.Dict(allow_none=True, description="Атрибуты субъекта")
    flag_keys = fields.List(fields.Str(), description="Список ключей флагов")


class DecisionItemSchema(Schema):
    value = fields.Raw(description="Значение флага")
    decision_id = fields.Str(allow_none=True, description="ID решения для атрибуции")
    experiment_id = fields.Str(allow_none=True)
    variant = fields.Str(allow_none=True)


class DecideResponseSchema(Schema):
    decisions = fields.Dict(description="Ключ — key флага, значение — объект {value, decision_id, experiment_id, variant}")
    status = fields.Str(allow_none=True)


class EventsSubmitResponseSchema(Schema):
    accepted = fields.Int(description="Принято событий")
    duplicates = fields.Int(description="Дубликатов")
    rejected = fields.Int(description="Отклонено")
    errors = fields.List(fields.Dict(), description="Ошибки по отклонённым")
    status = fields.Str(allow_none=True)


class EventTypeItemSchema(Schema):
    id = fields.Str()
    name = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    status = fields.Str(allow_none=True, description="Статус (например not_implemented)")


class EventTypesListResponseSchema(Schema):
    event_types = fields.List(fields.Nested(EventTypeItemSchema))
    status = fields.Str(allow_none=True)


class ReportExperimentResponseSchema(Schema):
    experiment_id = fields.Str()
    variants = fields.List(fields.Dict())
    metrics = fields.List(fields.Dict())
    status = fields.Str(allow_none=True)


class MetricsListResponseSchema(Schema):
    metrics = fields.List(fields.Dict())
    status = fields.Str(allow_none=True)