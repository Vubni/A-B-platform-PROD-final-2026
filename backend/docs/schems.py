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

class ExperimentMetricItemSchema(Schema):
    metric_key = fields.Str(required=True, description="Ключ метрики из каталога")
    metric_type = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("primary", "auxiliary", "guardrail")),
        description="Тип: primary (ровно один), auxiliary или guardrail",
    )


class ExperimentCreateSchema(Schema):
    flag_id = fields.Str(required=True, description="UUID флага")
    name = fields.Str(required=True, description="Название эксперимента, до 255 символов")
    audience_fraction = fields.Float(required=True, description="Доля аудитории в (0, 1]")
    targeting_rule = fields.Str(allow_none=True, description="Правило таргетинга, опционально")
    metrics = fields.List(
        fields.Nested(ExperimentMetricItemSchema),
        load_default=list,
        description="Метрики эксперимента: ровно одна primary, остальные auxiliary/guardrail. Все ключи должны быть в каталоге.",
    )


class ExperimentUpdateSchema(Schema):
    name = fields.Str(required=False, description="Новое название")
    audience_fraction = fields.Float(required=False, description="Новая доля аудитории (0, 1]")
    targeting_rule = fields.Str(required=False, allow_none=True)
    metrics = fields.List(
        fields.Nested(ExperimentMetricItemSchema),
        required=False,
        description="Новый список метрик (ровно одна primary). Передаётся только в draft.",
    )


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
    version = fields.Int(allow_none=True)
    created_by = fields.Str(allow_none=True)
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)
    variants = fields.List(fields.Nested(ExperimentVariantSchema), allow_none=True)
    metrics = fields.List(fields.Dict(), allow_none=True, description="Список {metric_key, metric_type, ...} из experiment_metrics")


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
    subject_id = fields.Str(required=True, description="Идентификатор субъекта (пользователя, устройства, сессии)")
    attributes = fields.Dict(allow_none=True, description="Атрибуты субъекта для таргетинга (произвольные ключ-значение)")
    flags = fields.List(fields.Str(), required=True, description="Список UUID флагов (минимум один)")


class DecideExperimentSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    variant = fields.Str(description="Название варианта (control, treatment и т.д.)")


class DecideFlagItemSchema(Schema):
    flag_key = fields.Str(description="Ключ (UUID) флага")
    flag_value = fields.Raw(description="Значение флага для этого субъекта (bool, число, строка — по типу флага)")
    decision_id = fields.Str(allow_none=True, description="UUID решения для атрибуции событий (если решение записывалось)")
    experiment = fields.Nested(DecideExperimentSchema, allow_none=True, description="Данные эксперимента, если субъект в эксперименте; иначе null")


class DecideResponseSchema(Schema):
    flags = fields.List(
        fields.Nested(DecideFlagItemSchema),
        description="Решения по флагам в том же порядке, что и в запросе"
    )


class EventSubmitItemSchema(Schema):
    event_id = fields.Str(required=True, description="Уникальный идентификатор события (идемпотентность)")
    decision_id = fields.Str(required=True, description="UUID решения (decision_id из /decide)")
    event_type_key = fields.Str(required=True, description="Ключ типа события (exposure, click и т.д.)")
    subject_id = fields.Str(required=True, description="Идентификатор субъекта")
    timestamp = fields.Str(required=True, description="Время события (ISO 8601)")
    payload = fields.Dict(load_default=dict, description="Доп. параметры события (по правилам типа)")


class EventsSubmitRequestSchema(Schema):
    events = fields.List(
        fields.Nested(EventSubmitItemSchema),
        required=True,
        description="Массив событий для отправки",
    )


class EventsSubmitResponseSchema(Schema):
    accepted = fields.Int(description="Принято событий")
    duplicates = fields.Int(description="Дубликатов")
    rejected = fields.Int(description="Отклонено")
    errors = fields.List(fields.Dict(), description="Ошибки по отклонённым")
    status = fields.Str(allow_none=True)


class EventTypeCreateSchema(Schema):
    key = fields.Str(required=True, description="Уникальный ключ типа (exposure, click, purchase и т.д.)")
    display_name = fields.Str(allow_none=True, description="Человекочитаемое имя")
    description = fields.Str(allow_none=True)
    required_params = fields.Raw(allow_none=True, description="Обязательные доп. параметры (JSON объект/схема)")
    validation_type = fields.Str(allow_none=True, description="Тип валидации (например: none, schema, payload_schema)")
    report_alert_config = fields.Raw(allow_none=True, description="Участие в отчётах/алертах: включение в отчёты, метрики, алерты, маршрутизация в стрим")
    requires_show_event_type_id = fields.Str(allow_none=True, description="UUID типа «факт показа» для атрибуции")
    is_critical = fields.Bool(load_default=False, description="Критичность события")


class EventTypeUpdateSchema(Schema):
    display_name = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    required_params = fields.Raw(allow_none=True)
    validation_type = fields.Str(allow_none=True)
    report_alert_config = fields.Raw(allow_none=True)
    requires_show_event_type_id = fields.Str(allow_none=True)
    is_critical = fields.Bool(allow_none=True)


class EventTypeItemSchema(Schema):
    id = fields.Str()
    key = fields.Str()
    display_name = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    required_params = fields.Raw(allow_none=True)
    validation_type = fields.Str(allow_none=True)
    report_alert_config = fields.Raw(allow_none=True)
    status = fields.Str()
    requires_show_event_type_id = fields.Str(allow_none=True, description="Тип события «факт показа» для атрибуции")
    is_critical = fields.Bool()
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class EventTypesListQuerySchema(Schema):
    status = fields.Str(
        required=False,
        validate=mvalidate.OneOf(("active", "archived")),
        description="Фильтр: active — только активные, archived — только архивированные",
    )


class EventTypesListResponseSchema(Schema):
    event_types = fields.List(fields.Nested(EventTypeItemSchema))



class MetricCatalogItemSchema(Schema):
    id = fields.Str(description="UUID метрики в каталоге")
    key = fields.Str(description="Уникальный ключ метрики (идентификатор)")
    name = fields.Str(description="Человекочитаемое название")
    description = fields.Str(allow_none=True, description="Назначение метрики")
    aggregation_rule = fields.Dict(
        description="Правило вычисления по событиям: kind (count_events, ratio, avg, percentile), event_type_key, aggregation_unit (subject|event), value_path и т.д."
    )
    attribution_rule = fields.Dict(
        allow_none=True,
        description="Условия атрибуции: requires_decision (требовать подтверждённый факт показа) и др.",
    )
    event_expectations = fields.Dict(
        allow_none=True,
        description="Ключи событий и ожидание: {event_type_key: 'higher'|'lower'}. Какие эвенты метрика смотрит; higher = рост лучше, lower = падение лучше.",
    )
    unit = fields.Str(allow_none=True, description="Единица измерения (events, ratio, ms и т.д.)")
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class MetricCatalogCreateSchema(Schema):
    key = fields.Str(required=True, description="Уникальный идентификатор метрики (латиница, цифры, подчёркивание)")
    name = fields.Str(required=True, description="Название метрики")
    description = fields.Str(allow_none=True, description="Назначение метрики")
    aggregation_rule = fields.Dict(
        required=True,
        description="Правило вычисления: какие события и как агрегируются (count_events, ratio, avg, percentile)",
    )
    attribution_rule = fields.Dict(
        allow_none=True,
        description="Условия атрибуции (например requires_decision для факта показа)",
    )
    event_expectations = fields.Dict(
        allow_none=True,
        description="Ключи событий и ожидание: {event_type_key: 'higher'|'lower'}. Какие эвенты метрика смотрит.",
    )
    unit = fields.Str(allow_none=True, description="Единица агрегации (events, ratio, ms)")


class MetricCatalogUpdateSchema(Schema):
    name = fields.Str(required=False, description="Новое название")
    description = fields.Str(required=False, allow_none=True)
    aggregation_rule = fields.Dict(required=False, description="Новое правило вычисления")
    attribution_rule = fields.Dict(required=False, allow_none=True)
    event_expectations = fields.Dict(required=False, allow_none=True, description="Ключи событий и ожидание")
    unit = fields.Str(required=False, allow_none=True)


class MetricsListResponseSchema(Schema):
    metrics = fields.List(
        fields.Nested(MetricCatalogItemSchema),
        description="Массив метрик из каталога",
    )
    status = fields.Str(allow_none=True)


class ReportWindowQuerySchema(Schema):
    start = fields.Str(required=True, description="Начало окна (ISO 8601), включительно")
    end = fields.Str(required=True, description="Конец окна (ISO 8601), не включительно")


class ReportMetricValueSchema(Schema):
    metric_key = fields.Str(description="Ключ метрики из каталога")
    value = fields.Raw(description="Вычисленное значение (число или null)")
    unit = fields.Str(allow_none=True)


class ReportVariantRowSchema(Schema):
    variant_id = fields.Str(description="UUID варианта")
    variant_name = fields.Str(description="Имя варианта (control, treatment и т.д.)")
    is_control = fields.Bool(description="Является ли контрольным")
    metric_values = fields.List(
        fields.Nested(ReportMetricValueSchema),
        description="Значения метрик для этого варианта",
    )
    event_counts = fields.Dict(
        description="Число срабатываний каждого типа событий (event_type_key -> count) у пользователей этого варианта",
    )


class ReportMetricDefinitionSchema(Schema):
    metric_key = fields.Str()
    metric_type = fields.Str(description="primary | auxiliary | guardrail")
    name = fields.Str(allow_none=True)
    unit = fields.Str(allow_none=True)
    event_expectations = fields.Dict(allow_none=True, description="Ожидание по ключам событий: higher|lower")


class ReportPrimaryMetricResultSchema(Schema):
    variant_id = fields.Str()
    variant_name = fields.Str()
    value = fields.Raw(allow_none=True)
    vs_control = fields.Str(description="better | worse | same")
    change_percent = fields.Float(allow_none=True)


class ReportPrimaryMetricSummarySchema(Schema):
    metric_key = fields.Str()
    metric_name = fields.Str()
    control_value = fields.Raw(allow_none=True)
    control_variant_name = fields.Str(allow_none=True)
    direction = fields.Str(allow_none=True, description="higher | lower — что считается «лучше»")
    results = fields.List(fields.Nested(ReportPrimaryMetricResultSchema), description="Сравнение вариантов с контролем")
    summary_lines = fields.List(
        fields.Str(),
        description="Краткие строки: «вариант: стало лучше/хуже на X%» по каждому варианту",
    )


class ReportContextSchema(Schema):
    window_start = fields.Str(description="Начало окна (включительно)")
    window_end = fields.Str(description="Конец окна (не включительно)")
    aggregation_unit = fields.Str(allow_none=True, description="Единица агрегации (subject | event) по метрикам")


class ReportMetricDynamicsItemSchema(Schema):
    period_start = fields.Str(description="Начало подпериода (ISO 8601)")
    period_end = fields.Str(description="Конец подпериода")
    value = fields.Raw()


class ReportExperimentResponseSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    experiment_name = fields.Str(allow_none=True, description="Название эксперимента")
    status = fields.Str(allow_none=True, description="Статус эксперимента")
    context = fields.Nested(
        ReportContextSchema,
        allow_none=True,
        description="Окно отчёта и единица агрегации",
    )
    metrics = fields.List(
        fields.Nested(ReportMetricDefinitionSchema),
        description="Метрики, выбранные для эксперимента (основная и дополнительные)",
    )
    variants = fields.List(
        fields.Nested(ReportVariantRowSchema),
        description="Значения метрик и число срабатываний событий по каждому варианту",
    )
    primary_metric_summary = fields.Nested(
        ReportPrimaryMetricSummarySchema,
        allow_none=True,
        description="Сводка по главной метрике: лучше/хуже по каждому варианту относительно контроля и на сколько",
    )
    dynamics = fields.List(
        fields.Dict(),
        allow_none=True,
        description="Динамика метрик в выбранном диапазоне (если запрошена)",
    )


METRIC_CATALOG_CREATE_REQUEST_EXAMPLE = {
    "key": "add_to_favorites_rate",
    "name": "Доля добавивших в избранное",
    "description": "Доля пользователей, добавивших товар в избранное после показа.",
    "aggregation_rule": {
        "kind": "ratio",
        "numerator_metric_key": "add_to_favorites",
        "denominator_metric_key": "impressions",
        "aggregation_unit": "subject",
    },
    "attribution_rule": {"requires_decision": True},
    "unit": "ratio",
}

REPORT_WINDOW_QUERY_EXAMPLE = {
    "start": "2025-02-01T00:00:00Z",
    "end": "2025-02-18T00:00:00Z",
}