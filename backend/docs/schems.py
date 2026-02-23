from marshmallow import Schema, fields
from marshmallow import validate as mvalidate


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
    experimenter_id = fields.Str(
        required=False, allow_none=True, description="UUID экспериментатора или null"
    )
    min_approvals = fields.Int(load_default=1, description="Минимум одобрений")
    approver_ids = fields.List(fields.Str(), load_default=list, description="UUID аппруверов")


class ApproverGroupUpdateSchema(Schema):
    min_approvals = fields.Int(required=False, description="Минимум одобрений")
    approver_ids = fields.List(
        fields.Str(), required=False, description="Новый список UUID аппруверов"
    )


class ApproverGroupItemSchema(Schema):
    id = fields.Str()
    experimenter_id = fields.Str(allow_none=True)
    min_approvals = fields.Int()
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class ApproverGroupListResponseSchema(Schema):
    approver_groups = fields.List(fields.Nested(ApproverGroupItemSchema))


class FlagCreateSchema(Schema):
    key = fields.Str(
        required=True, description="Уникальный ключ флага (буква, цифры, подчёркивание)"
    )
    value_type = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("string", "number", "bool")),
        description="Тип значения: string, number, bool",
    )
    default_value = fields.Str(
        required=True, description="Значение по умолчанию при отсутствии эксперимента"
    )
    description = fields.Str(allow_none=True, description="Описание флага")
    owner = fields.Str(allow_none=True, description="Владелец/команда")
    metadata = fields.Dict(allow_none=True, description="Произвольные метаданные")


class FlagUpdateSchema(Schema):
    default_value = fields.Str(
        required=True, description="Новое значение по умолчанию (только это поле можно обновить)"
    )


class ErrorDetailSchema(Schema):
    name = fields.Str(description="Имя параметра, вызвавшего ошибку")
    type = fields.Str(description="Тип ошибки (например, missing)")
    message = fields.Str(description="Сообщение об ошибке")
    value = fields.Raw(description="Значение параметра, если оно было передано", allow_none=True)


class FieldErrorItemSchema(Schema):
    field = fields.Str(description="Поле с ошибкой")
    issue = fields.Str(description="Описание ошибки")
    rejectedValue = fields.Raw(allow_none=True, description="Отклонённое значение")


class HttpErrorSchema(Schema):
    code = fields.Str(description="Код ошибки (UNAUTHORIZED, FORBIDDEN, NOT_FOUND, ...)")
    message = fields.Str(description="Сообщение об ошибке")
    traceId = fields.Str(description="Идентификатор запроса для отладки")
    timestamp = fields.Str(description="Время ответа в ISO 8601")
    path = fields.Str(description="Путь запроса")
    details = fields.Dict(allow_none=True, description="Дополнительные данные (опционально)")
    fieldErrors = fields.List(
        fields.Nested(FieldErrorItemSchema),
        allow_none=True,
        description="Ошибки по полям при 422 (опционально)",
    )


RESPONSES_HTTP_ERROR = {
    400: {"description": "Некорректный запрос", "schema": HttpErrorSchema},
    401: {"description": "Не авторизован", "schema": HttpErrorSchema},
    403: {"description": "Нет прав", "schema": HttpErrorSchema},
    404: {"description": "Не найдено", "schema": HttpErrorSchema},
    409: {"description": "Конфликт (дубликат и т.п.)", "schema": HttpErrorSchema},
    422: {"description": "Ошибка валидации", "schema": HttpErrorSchema},
    500: {"description": "Внутренняя ошибка сервера", "schema": HttpErrorSchema},
}


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
    "approver_ids": [
        "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "c3d4e5f6-a7b8-9012-cdef-123456789012",
    ],
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
        validate=mvalidate.OneOf(
            (
                "draft",
                "on_review",
                "approved",
                "running",
                "paused",
                "archived",
                "rejected",
            )
        ),
        description="Новый статус (completed задаётся отдельным эндпоинтом POST .../complete)",
    )
    comment = fields.Str(allow_none=True, description="Комментарий (для ревью)")


class CompleteExperimentSchema(Schema):
    completion_outcome = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("rollout_winner", "rollback", "no_effect")),
        description="Режим завершения: rollout_winner — раскатить победителя; rollback — откат к контролю; no_effect — эффект не выявлен",
    )
    comment = fields.Str(required=True, description="Обоснование решения и что делать с гипотезой")
    completion_winner_variant_id = fields.Str(
        load_default=None,
        allow_none=True,
        description="UUID варианта-победителя (обязателен при completion_outcome=rollout_winner)",
    )


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
    metrics = fields.List(
        fields.Dict(),
        allow_none=True,
        description="Список {metric_key, metric_type, ...} из experiment_metrics",
    )


class ExperimentListResponseSchema(Schema):
    experiments = fields.List(
        fields.Nested(ExperimentItemSchema), description="Массив экспериментов"
    )


class GuardrailHistoryResponseSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    triggers = fields.List(fields.Dict(), description="История срабатываний guardrail")


class LearningGuardrailItemSchema(Schema):
    metric_key = fields.Str(description="Ключ guardrail-метрики")
    threshold_value = fields.Float(allow_none=True, description="Порог guardrail, если задан")
    trigger_count = fields.Int(description="Сколько раз guardrail срабатывал")
    details = fields.Dict(allow_none=True, description="Дополнительный контекст")
    created_at = fields.Str(allow_none=True)


class LearningUpsertSchema(Schema):
    owner_user_id = fields.Str(allow_none=True, description="UUID владельца записи")
    owner_team = fields.Str(allow_none=True, description="Команда-владелец")
    hypothesis = fields.Str(required=True, description="Гипотеза эксперимента")
    primary_metric_key = fields.Str(required=True, description="Ключ основной метрики")
    result_outcome = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("rollout_winner", "rollback", "no_effect", "worse")),
        description="Итог эксперимента",
    )
    result_action = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("rollout", "rollback", "continue", "repeat")),
        description="Что сделали после эксперимента",
    )
    effect_summary = fields.Str(allow_none=True, description="Краткий эффект по основной метрике")
    targeting_summary = fields.Str(allow_none=True, description="Краткое описание таргетинга")
    platforms = fields.List(fields.Str(), load_default=list, description="Платформы")
    countries = fields.List(fields.Str(), load_default=list, description="Страны")
    app_versions = fields.List(fields.Str(), load_default=list, description="Версии приложения")
    product_tags = fields.List(fields.Str(), load_default=list, description="Теги продуктовой зоны")
    change_type = fields.Str(allow_none=True, description="Тип изменения")
    variant_structure = fields.Dict(
        load_default=dict,
        description="Структура вариантов (A/B/n, rollout, веса и т.д.)",
    )
    report_url = fields.Str(allow_none=True, description="Ссылка на отчёт/дашборд")
    ticket_url = fields.Str(allow_none=True, description="Ссылка на тикет/PRD")
    notes = fields.Str(required=True, description="Короткие выводы why/why not")
    is_completed = fields.Bool(
        load_default=False, description="Признак, что learning заполнен полностью"
    )
    guardrails = fields.List(
        fields.Nested(LearningGuardrailItemSchema),
        load_default=list,
        description="Guardrail-сводка по эксперименту",
    )


class LearningItemSchema(Schema):
    id = fields.Str(description="UUID learning")
    experiment_id = fields.Str(description="UUID эксперимента")
    experiment_name = fields.Str(allow_none=True)
    experiment_status = fields.Str(allow_none=True)
    flag_key = fields.Str()
    owner_user_id = fields.Str(allow_none=True)
    owner_team = fields.Str(allow_none=True)
    hypothesis = fields.Str()
    primary_metric_key = fields.Str()
    result_outcome = fields.Str()
    result_action = fields.Str()
    effect_summary = fields.Str(allow_none=True)
    guardrail_triggers_count = fields.Int()
    targeting_summary = fields.Str(allow_none=True)
    platforms = fields.List(fields.Str())
    countries = fields.List(fields.Str())
    app_versions = fields.List(fields.Str())
    product_tags = fields.List(fields.Str())
    change_type = fields.Str(allow_none=True)
    variant_structure = fields.Dict()
    report_url = fields.Str(allow_none=True)
    ticket_url = fields.Str(allow_none=True)
    notes = fields.Str()
    is_completed = fields.Bool()
    created_by = fields.Str(allow_none=True)
    updated_by = fields.Str(allow_none=True)
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)
    guardrails = fields.List(fields.Nested(LearningGuardrailItemSchema), allow_none=True)


class LearningListResponseSchema(Schema):
    learnings = fields.List(fields.Nested(LearningItemSchema), description="Список learnings")


class LearningListQuerySchema(Schema):
    q = fields.Str(required=False, description="Полнотекстовый поиск")
    flag_key = fields.Str(required=False)
    owner_user_id = fields.Str(required=False)
    owner_team = fields.Str(required=False)
    result_outcome = fields.Str(
        required=False,
        validate=mvalidate.OneOf(("rollout_winner", "rollback", "no_effect", "worse")),
    )
    primary_metric_key = fields.Str(required=False)
    countries = fields.Str(required=False, description="CSV стран: RU,US")
    platforms = fields.Str(required=False, description="CSV платформ: ios,android,web")
    tags = fields.Str(required=False, description="CSV тегов продуктовой зоны")
    date_from = fields.Str(required=False, description="ISO дата начала фильтра")
    date_to = fields.Str(required=False, description="ISO дата конца фильтра")
    limit = fields.Int(required=False, load_default=20)
    offset = fields.Int(required=False, load_default=0)


class LearningAuditItemSchema(Schema):
    id = fields.Str()
    learning_id = fields.Str(allow_none=True)
    action = fields.Str()
    changed_by = fields.Str(allow_none=True)
    changed_at = fields.Str(allow_none=True)
    before_state = fields.Dict(allow_none=True)
    after_state = fields.Dict(allow_none=True)


class LearningAuditListResponseSchema(Schema):
    learning_id = fields.Str()
    audit = fields.List(fields.Nested(LearningAuditItemSchema))


class LearningSimilarItemSchema(Schema):
    score = fields.Float(description="Итоговый similarity-score (0..1)")
    reasons = fields.List(
        fields.Str(),
        allow_none=True,
        description="Краткие причины похожести (совпадающие признаки)",
    )
    learning = fields.Nested(LearningItemSchema)


class LearningSimilarResponseSchema(Schema):
    learning_id = fields.Str()
    similar = fields.List(fields.Nested(LearningSimilarItemSchema))


class ExperimentGuardrailItemSchema(Schema):
    metric_key = fields.Str(description="Ключ guardrail-метрики из каталога")
    threshold = fields.Float(description="Порог, при превышении которого срабатывает guardrail")
    window_seconds = fields.Int(description="Окно наблюдения в секундах (> 0)")
    action = fields.Str(description="Действие при срабатывании: pause | rollback_to_control")
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class ExperimentGuardrailUpsertSchema(Schema):
    metric_key = fields.Str(required=True, description="Ключ guardrail-метрики эксперимента")
    threshold = fields.Float(required=True, description="Порог метрики для срабатывания guardrail")
    window_seconds = fields.Int(required=True, description="Окно наблюдения в секундах (> 0)")
    action = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("pause", "rollback_to_control")),
        description="Действие при срабатывании: pause или rollback_to_control",
    )


class ExperimentGuardrailListResponseSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    guardrails = fields.List(
        fields.Nested(ExperimentGuardrailItemSchema), description="Guardrail-правила эксперимента"
    )


class RampPlanStepSchema(Schema):
    step_index = fields.Int(
        description="Порядковый индекс ступени (0..N), определяет последовательность раскатки"
    )
    traffic_fraction = fields.Float(
        description="Целевая доля аудитории эксперимента на этой ступени (0, 1]"
    )


class RampSafetyActionSchema(Schema):
    trigger_type = fields.Str(
        validate=mvalidate.OneOf(
            ("guardrail_triggered", "error_rate_high", "latency_high", "data_quality_critical")
        ),
        description="Событие-триггер, при котором запускается safety-реакция",
    )
    action = fields.Str(
        validate=mvalidate.OneOf(("pause", "rollback_to_control", "step_back")),
        description="Какой защитный шаг выполнить при срабатывании триггера",
    )


class RampPlanGateDataSufficiencySchema(Schema):
    min_total_impressions = fields.Int(description="Минимум показов на шаге (в сумме)")
    min_impressions_per_variant = fields.Int(description="Минимум показов на каждый вариант")
    min_minutes_on_step = fields.Int(description="Минимальное время на текущей ступени (минуты)")


class RampPlanGateSafetySchema(Schema):
    use_guardrails = fields.Bool(description="Учитывать guardrail-срабатывания при автооценке")
    error_rate_threshold = fields.Float(description="Порог error_rate для safety gate")
    latency_p95_ms = fields.Float(description="Порог p95 latency в миллисекундах")


class RampPlanGateDataHealthSchema(Schema):
    require_no_srm = fields.Bool(description="Требовать отсутствие SRM")
    require_no_mass_rejected = fields.Bool(
        description="Требовать отсутствие массово отклонённых событий"
    )


class RampPlanSchema(Schema):
    id = fields.Str(description="UUID ramp-плана (идентификатор ресурса)")
    experiment_id = fields.Str(description="UUID эксперимента, к которому относится план")
    observation_window_seconds = fields.Int(
        description="Длина окна наблюдения в секундах перед автоматической оценкой перехода на следующую ступень"
    )
    gate_data_sufficiency = fields.Nested(
        RampPlanGateDataSufficiencySchema,
        description="Gate: достаточность данных перед переходом между ступенями",
    )
    gate_safety = fields.Nested(
        RampPlanGateSafetySchema, description="Gate: условия безопасности раскатки"
    )
    gate_data_health = fields.Nested(
        RampPlanGateDataHealthSchema, description="Gate: проверка качества данных"
    )
    steps = fields.List(
        fields.Nested(RampPlanStepSchema),
        description="Бизнес-представление ступеней раскатки (только order + traffic), отсортировано по step_index",
    )
    safety_actions = fields.List(
        fields.Nested(RampSafetyActionSchema),
        description="Набор защитных реакций на критические сигналы качества/безопасности",
    )
    created_at = fields.Str(
        allow_none=True, description="Когда ramp-план был создан (техническое поле аудита)"
    )
    updated_at = fields.Str(
        allow_none=True,
        description="Когда ramp-план в последний раз обновлялся (техническое поле аудита)",
    )


class RampPlanStepUpsertSchema(Schema):
    step_index = fields.Int(
        required=False,
        description="Индекс ступени. Если не задан, выставляется автоматически по позиции в массиве",
    )
    traffic_fraction = fields.Float(required=True, description="Доля трафика на ступени (0, 1]")


class RampSafetyActionUpsertSchema(Schema):
    trigger_type = fields.Str(
        required=True,
        validate=mvalidate.OneOf(
            ("guardrail_triggered", "error_rate_high", "latency_high", "data_quality_critical")
        ),
        description="Триггер, при котором выполняется safety action",
    )
    action = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("pause", "rollback_to_control", "step_back")),
        description="Действие при триггере",
    )


class RampPlanPutSchema(Schema):
    observation_window_seconds = fields.Int(
        required=True, description="Окно наблюдения в секундах (> 0)"
    )
    steps = fields.List(
        fields.Nested(RampPlanStepUpsertSchema),
        required=True,
        description="Список ступеней раскатки (минимум одна)",
    )
    gate_data_sufficiency = fields.Nested(
        RampPlanGateDataSufficiencySchema,
        required=False,
        description="Настройки gate достаточности данных (опционально)",
    )
    gate_safety = fields.Nested(
        RampPlanGateSafetySchema,
        required=False,
        description="Настройки gate безопасности (опционально)",
    )
    gate_data_health = fields.Nested(
        RampPlanGateDataHealthSchema,
        required=False,
        description="Настройки gate качества данных (опционально)",
    )
    safety_actions = fields.List(
        fields.Nested(RampSafetyActionUpsertSchema),
        required=False,
        description="Правила safety actions (опционально)",
    )


class RampStateSchema(Schema):
    experiment_id = fields.Str(
        description="UUID эксперимента, для которого работает runtime-состояние"
    )
    ramp_plan_id = fields.Str(description="UUID активного ramp-плана, по которому идёт управление")
    current_step_index = fields.Int(
        description="Текущая применённая ступень (индекс из steps), определяет текущую долю трафика"
    )
    mode = fields.Str(
        validate=mvalidate.OneOf(("autopilot", "manual", "paused")),
        description="Режим работы автопилота",
    )
    started_at = fields.Str(
        allow_none=True, description="Когда автопилот был впервые запущен для эксперимента"
    )
    step_entered_at = fields.Str(
        allow_none=True,
        description="Когда вошли на текущую ступень (для gate min_minutes_on_step)",
    )
    last_eval_at = fields.Str(
        allow_none=True, description="Время последней автоматической/ручной оценки состояния"
    )
    manual_override_by_user_id = fields.Str(
        allow_none=True, description="UUID пользователя, изменившего ступень/режим вручную"
    )
    manual_override_at = fields.Str(
        allow_none=True, description="Когда последний раз выполнялось ручное вмешательство"
    )
    updated_at = fields.Str(
        allow_none=True,
        description="Последнее обновление записи состояния (техническое поле аудита)",
    )


class RampModePatchSchema(Schema):
    mode = fields.Str(
        required=True,
        validate=mvalidate.OneOf(("autopilot", "manual", "paused")),
        description="Новый режим работы: autopilot | manual | paused",
    )


class RampOverridePostSchema(Schema):
    to_step_index = fields.Int(required=True, description="Индекс целевой ступени (>= 0)")


class RampDecisionLogItemSchema(Schema):
    id = fields.Str(description="UUID записи лога решения")
    experiment_id = fields.Str(description="UUID эксперимента, к которому относится решение")
    decided_at = fields.Str(description="Момент принятия решения (временная ось логов)")
    action = fields.Str(
        validate=mvalidate.OneOf(
            (
                "start",
                "resume",
                "step_up",
                "step_back",
                "pause",
                "rollback",
                "override",
                "no_change",
            )
        ),
        description="Тип решения автопилота",
    )
    from_step_index = fields.Int(description="Индекс ступени до изменения")
    to_step_index = fields.Int(
        allow_none=True, description="Индекс ступени после изменения (null для no_change)"
    )
    reason = fields.Dict(
        description="Причины/контекст решения: результаты gate-проверок, служебные детали"
    )
    triggered_by = fields.Str(description="Кто инициировал решение: autopilot | manual")
    user_id = fields.Str(
        allow_none=True, description="UUID пользователя для manual-действий, иначе null"
    )
    created_at = fields.Str(allow_none=True)


class RampDecisionLogResponseSchema(Schema):
    decisions = fields.List(
        fields.Nested(RampDecisionLogItemSchema), description="Лента решений по автопилот-раскатке"
    )


RAMP_PLAN_PUT_REQUEST_EXAMPLE = {
    "observation_window_seconds": 3600,
    "steps": [
        {"step_index": 0, "traffic_fraction": 0.05},
        {"step_index": 1, "traffic_fraction": 0.2},
        {"step_index": 2, "traffic_fraction": 0.5},
        {"step_index": 3, "traffic_fraction": 1.0},
    ],
    "gate_data_sufficiency": {
        "min_total_impressions": 1000,
        "min_impressions_per_variant": 200,
        "min_minutes_on_step": 60,
    },
    "gate_safety": {
        "use_guardrails": True,
        "error_rate_threshold": 0.01,
        "latency_p95_ms": 500,
    },
    "gate_data_health": {
        "require_no_srm": True,
        "require_no_mass_rejected": True,
    },
    "safety_actions": [
        {"trigger_type": "guardrail_triggered", "action": "pause", "notify": True},
        {"trigger_type": "error_rate_high", "action": "step_back", "notify": True},
    ],
}

RAMP_PLAN_RESPONSE_EXAMPLE = {
    "id": "d4e5f6a7-b8c9-4012-9abc-def123456789",
    "experiment_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "observation_window_seconds": 3600,
    "gate_data_sufficiency": {
        "min_total_impressions": 1000,
        "min_impressions_per_variant": 200,
        "min_minutes_on_step": 60,
    },
    "gate_safety": {
        "use_guardrails": True,
        "error_rate_threshold": 0.01,
        "latency_p95_ms": 500,
    },
    "gate_data_health": {
        "require_no_srm": True,
        "require_no_mass_rejected": True,
    },
    "steps": [
        {
            "step_index": 0,
            "traffic_fraction": 0.05,
        },
        {
            "step_index": 1,
            "traffic_fraction": 0.2,
        },
    ],
    "safety_actions": [
        {
            "trigger_type": "guardrail_triggered",
            "action": "pause",
            "notify": True,
        }
    ],
    "created_at": "2026-02-20T11:10:00Z",
    "updated_at": "2026-02-20T11:10:00Z",
}

RAMP_STATE_RESPONSE_EXAMPLE = {
    "experiment_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "ramp_plan_id": "d4e5f6a7-b8c9-4012-9abc-def123456789",
    "current_step_index": 1,
    "mode": "autopilot",
    "started_at": "2026-02-20T11:20:00Z",
    "step_entered_at": "2026-02-20T11:45:00Z",
    "last_eval_at": "2026-02-20T12:00:00Z",
    "manual_override_by_user_id": None,
    "manual_override_at": None,
    "updated_at": "2026-02-20T12:00:00Z",
}

RAMP_MODE_PATCH_REQUEST_EXAMPLE = {"mode": "manual"}

RAMP_OVERRIDE_POST_REQUEST_EXAMPLE = {"to_step_index": 2}

RAMP_DECISION_LOG_RESPONSE_EXAMPLE = {
    "decisions": [
        {
            "id": "b8c9d0e1-f2a3-4456-def1-234567890123",
            "experiment_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
            "decided_at": "2026-02-20T11:20:00Z",
            "action": "start",
            "from_step_index": 0,
            "to_step_index": 0,
            "reason": {"message": "autopilot started"},
            "triggered_by": "autopilot",
            "user_id": None,
            "created_at": "2026-02-20T11:20:00Z",
        },
        {
            "id": "c9d0e1f2-a3b4-4567-ef12-345678901234",
            "experiment_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
            "decided_at": "2026-02-20T12:00:00Z",
            "action": "step_up",
            "from_step_index": 0,
            "to_step_index": 1,
            "reason": {"gate_data_sufficiency": True, "gate_safety": True},
            "triggered_by": "autopilot",
            "user_id": None,
            "created_at": "2026-02-20T12:00:00Z",
        },
    ]
}


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
    subject_id = fields.Str(
        required=True, description="Идентификатор субъекта (пользователя, устройства, сессии)"
    )
    attributes = fields.Dict(
        allow_none=True,
        description="Атрибуты субъекта для таргетинга (произвольные ключ-значение)",
    )
    flags = fields.List(
        fields.Str(), required=True, description="Список UUID флагов (минимум один)"
    )


class DecideExperimentSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    variant = fields.Str(description="Название варианта (control, treatment и т.д.)")


class DecideFlagItemSchema(Schema):
    flag_key = fields.Str(description="Ключ (UUID) флага")
    flag_value = fields.Raw(
        description="Значение флага для этого субъекта (bool, число, строка — по типу флага)"
    )
    decision_id = fields.Str(
        allow_none=True,
        description="UUID решения для атрибуции событий (если решение записывалось)",
    )
    experiment = fields.Nested(
        DecideExperimentSchema,
        allow_none=True,
        description="Данные эксперимента, если субъект в эксперименте; иначе null",
    )
    conflict_lost = fields.Bool(
        allow_none=True,
        description="True, если эксперимент по флагу проиграл конфликт в домене",
    )
    conflict_domain = fields.Str(
        allow_none=True,
        description="Ключ домена конфликта, если conflict_lost=True",
    )


class DecideResponseSchema(Schema):
    flags = fields.List(
        fields.Nested(DecideFlagItemSchema),
        description="Решения по флагам в том же порядке, что и в запросе",
    )


class EventSubmitItemSchema(Schema):
    event_id = fields.Str(
        required=True, description="Уникальный идентификатор события (идемпотентность)"
    )
    decision_id = fields.Str(required=True, description="UUID решения (decision_id из /decide)")
    event_type_key = fields.Str(
        required=True, description="Ключ типа события (exposure, click и т.д.)"
    )
    subject_id = fields.Str(required=True, description="Идентификатор субъекта")
    timestamp = fields.Str(required=True, description="Время события (ISO 8601)")
    payload = fields.Dict(
        load_default=dict, description="Доп. параметры события (по правилам типа)"
    )


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
    key = fields.Str(
        required=True, description="Уникальный ключ типа (exposure, click, purchase и т.д.)"
    )
    display_name = fields.Str(allow_none=True, description="Человекочитаемое имя")
    description = fields.Str(allow_none=True)
    required_params = fields.Raw(
        allow_none=True, description="Обязательные доп. параметры (JSON объект/схема)"
    )
    validation_type = fields.Str(
        allow_none=True, description="Тип валидации (например: none, schema, payload_schema)"
    )
    report_alert_config = fields.Raw(
        allow_none=True,
        description="Участие в отчётах/алертах: включение в отчёты, метрики, алерты, маршрутизация в стрим",
    )
    requires_show_event_type_id = fields.Str(
        allow_none=True, description="UUID типа «факт показа» для атрибуции"
    )
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
    requires_show_event_type_id = fields.Str(
        allow_none=True, description="Тип события «факт показа» для атрибуции"
    )
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
    key = fields.Str(
        required=True,
        description="Уникальный идентификатор метрики (латиница, цифры, подчёркивание)",
    )
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
    event_expectations = fields.Dict(
        required=False, allow_none=True, description="Ключи событий и ожидание"
    )
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
    event_expectations = fields.Dict(
        allow_none=True, description="Ожидание по ключам событий: higher|lower"
    )


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
    results = fields.List(
        fields.Nested(ReportPrimaryMetricResultSchema),
        description="Сравнение вариантов с контролем",
    )
    summary_lines = fields.List(
        fields.Str(),
        description="Краткие строки: «вариант: стало лучше/хуже на X%» по каждому варианту",
    )
    recommendation = fields.Str(
        description="Рекомендация: keep_control — оставить дефолтный вариант; rollout — раскатить победителя",
    )
    winner_variant_id = fields.Str(
        allow_none=True, description="UUID варианта-победителя при recommendation=rollout"
    )
    winner_variant_name = fields.Str(
        allow_none=True, description="Название варианта-победителя при recommendation=rollout"
    )


class ReportContextSchema(Schema):
    window_start = fields.Str(description="Начало окна (включительно)")
    window_end = fields.Str(description="Конец окна (не включительно)")
    aggregation_unit = fields.Str(
        allow_none=True, description="Единица агрегации (subject | event) по метрикам"
    )


class ReportMetricDynamicsItemSchema(Schema):
    period_start = fields.Str(description="Начало подпериода (ISO 8601)")
    period_end = fields.Str(description="Конец подпериода")
    value = fields.Raw()


class ReportCompletionSchema(Schema):
    outcome = fields.Str(
        description="Режим завершения: rollout_winner — раскатить победителя; rollback — откат к контролю; no_effect — эффект не выявлен",
    )
    comment = fields.Str(
        allow_none=True, description="Обоснование решения и что делать с гипотезой"
    )
    winner_variant_id = fields.Str(
        allow_none=True, description="UUID варианта-победителя при outcome=rollout_winner"
    )
    winner_variant_name = fields.Str(
        allow_none=True, description="Название варианта-победителя при outcome=rollout_winner"
    )


class ReportExperimentResponseSchema(Schema):
    experiment_id = fields.Str(description="UUID эксперимента")
    experiment_name = fields.Str(allow_none=True, description="Название эксперимента")
    status = fields.Str(allow_none=True, description="Статус эксперимента")
    result = fields.Str(
        allow_none=True,
        description="Явный результат при status=completed: rollout — раскат победителя; rollback — откат к контролю; no_effect — эффект не выявлен. Иначе null.",
    )
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
    completion = fields.Nested(
        ReportCompletionSchema,
        allow_none=True,
        description="Финальное решение при status=completed: rollout_winner | rollback | no_effect и комментарий",
    )
    conflict_stats = fields.Nested(
        "ReportConflictStatsSchema",
        allow_none=True,
        description="Статистика конфликтов в окне: times_winner, times_loser",
    )


class ReportConflictStatsSchema(Schema):
    times_winner = fields.Int(
        description="Число решений, где эксперимент выиграл конфликт в домене"
    )
    times_loser = fields.Int(
        description="Число решений, где эксперимент проиграл конфликт в домене"
    )


class ConflictDomainItemSchema(Schema):
    id = fields.Str(description="UUID домена")
    key = fields.Str(description="Уникальный ключ домена (checkout, search_ranking и т.д.)")
    name = fields.Str(description="Название")
    description = fields.Str(allow_none=True)
    default_policy = fields.Str(
        validate=mvalidate.OneOf(("mutual_exclusion", "bid", "priority")),
        description="Политика по умолчанию для домена",
    )
    config_version = fields.Int()
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class ConflictDomainListResponseSchema(Schema):
    conflict_domains = fields.List(
        fields.Nested(ConflictDomainItemSchema),
        description="Список конфликтных доменов",
    )


class ConflictDomainCreateSchema(Schema):
    key = fields.Str(required=True, description="Уникальный ключ домена")
    name = fields.Str(required=True, description="Название")
    description = fields.Str(allow_none=True)
    default_policy = fields.Str(
        load_default="mutual_exclusion",
        validate=mvalidate.OneOf(("mutual_exclusion", "bid", "priority")),
    )


class ConflictDomainUpdateSchema(Schema):
    name = fields.Str(required=False)
    description = fields.Str(required=False, allow_none=True)
    default_policy = fields.Str(
        required=False,
        validate=mvalidate.OneOf(("mutual_exclusion", "bid", "priority")),
    )


class ConflictBindingItemSchema(Schema):
    experiment_id = fields.Str()
    domain_id = fields.Str()
    domain_key = fields.Str(allow_none=True)
    domain_name = fields.Str(allow_none=True)
    policy = fields.Str(allow_none=True)
    priority_tier = fields.Int(allow_none=True)
    bid_value = fields.Float()
    is_enabled = fields.Bool()
    created_at = fields.Str(allow_none=True)
    updated_at = fields.Str(allow_none=True)


class ConflictBindingListResponseSchema(Schema):
    bindings = fields.List(
        fields.Nested(ConflictBindingItemSchema),
        description="Привязки эксперимента к конфликтным доменам",
    )


class ConflictBindingUpsertSchema(Schema):
    domain_id = fields.Str(required=True, description="UUID домена")
    policy = fields.Str(
        allow_none=True,
        validate=mvalidate.OneOf(("mutual_exclusion", "bid", "priority")),
    )
    priority_tier = fields.Int(allow_none=True)
    bid_value = fields.Float(load_default=0)
    is_enabled = fields.Bool(load_default=True)


class ConflictPreflightItemSchema(Schema):
    domain_id = fields.Str()
    domain_key = fields.Str()
    domain_name = fields.Str()
    conflicting_experiments = fields.List(fields.Dict())


class ConflictPreflightResponseSchema(Schema):
    conflict_warnings = fields.List(
        fields.Nested(ConflictPreflightItemSchema),
        description="Домены, в которых запуск создаст конфликт с уже running экспериментами",
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
