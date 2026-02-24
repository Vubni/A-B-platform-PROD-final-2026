# Пакет тестовых данных и демо-сценариев

Контролируемые данные и сценарии для проверки happy-path, негативных и граничных случаев.  
Предусловия: после `python tests/seed_test_data.py` доступны пользователи, флаг `test_feature_flag`, типы событий `demo_exposure` / `demo_click` / `demo_conversion`, метрики и группа аппруверов для experimenter.

---

## Предусловия

| Что | Как получить |
|-----|----------------|
| Запущенный backend и БД | `docker compose up -d` или локальный запуск по `backend/README.md` |
| Тестовые данные | `export API_BASE_URL=http://localhost:80` и `python tests/seed_test_data.py` |
| Токен admin | `POST /api/v1/auth` с `{"email": "admin@test.com", "password": "admin123"}` → `token` |
| Токен experimenter | `{"email": "experimenter@test.com", "password": "exp123"}` |
| Токен viewer | `{"email": "viewer@test.com", "password": "view123"}` |
| Токен approver | `{"email": "approver@test.com", "password": "app123"}` |

Фиксированные ключи после сида:
- Флаг: `test_feature_flag`
- Типы событий: `demo_exposure`, `demo_click`, `demo_conversion` (conversion зависит от exposure)
- Метрики: `demo_impressions`, `demo_conversions`, `demo_conversion_rate`

---

## 1. Позитивные сценарии (happy-path)

### 1.1 Сквозной путь: флаг → эксперимент → decide → события → отчёт

**Цель:** убедиться, что выдача варианта, приём событий и отчёт работают в связке.

**Шаги:**

1. Взять `flag_id` и `flag_key` флага `test_feature_flag`: `GET /api/v1/flags` (с заголовком `Authorization: Bearer <admin_token>`) → в ответе найти объект с `"key": "test_feature_flag"`, скопировать `id` (для `flag_id`) и использовать `"key"` как `flag_key` в `/decide`.
2. Создать эксперимент от experimenter:  
   `POST /api/v1/experiments` с телом:
   ```json
   {
     "flag_id": "<flag_id>",
     "name": "Demo A/B",
     "audience_fraction": 1.0,
     "metrics": [
       {"metric_key": "demo_conversion_rate", "metric_type": "primary"},
       {"metric_key": "demo_impressions", "metric_type": "auxiliary"}
     ]
   }
   ```
   Ожидаемо: **201**, в теле `id` эксперимента.
3. Добавить варианты:  
   `POST /api/v1/experiments/{experiment_id}/variants` дважды:
   - `{"variant_name": "control", "variant_value": "c", "weight": 0.5, "is_control": true}`
   - `{"variant_name": "treatment", "variant_value": "t", "weight": 0.5, "is_control": false}`  
   Ожидаемо: **201** на каждый.
4. Отправить на ревью: `PATCH /api/v1/experiments/{id}/status` с `{"new_status": "on_review"}`. Ожидаемо: **200**.
5. Одобрить от approver: `PATCH /api/v1/experiments/{id}/status` с `{"new_status": "approved"}` (от имени approver). Ожидаемо: **200**.
6. Запустить: `PATCH /api/v1/experiments/{id}/status` с `{"new_status": "running"}`. Ожидаемо: **200**.
7. Выдать вариант: `POST /api/v1/decide` с `{"subject_id": "u42", "attributes": {}, "flags": ["test_feature_flag"]}` (или соответствующим `flag_key`).  
   Ожидаемо: **200**, в `flags` один элемент с `flag_value` ("c" или "t"), `decision_id`, `experiment_id`, `variant_id`.
8. Отправить экспозицию: `POST /api/v1/events` с телом:
   ```json
   {
     "events": [{
       "event_id": "ev-demo-1",
       "decision_id": "<decision_id из шага 7>",
       "event_type_key": "demo_exposure",
       "subject_id": "u42",
       "timestamp": "2026-02-14T12:00:00Z"
     }]
   }
   ```
   Ожидаемо: **200**, в `accepted` один элемент с тем же `event_id`.
9. Отправить конверсию: то же, но `event_type_key": "demo_conversion"`, `event_id": "ev-demo-2"`. Ожидаемо: **200**, событие принято.
10. Запросить отчёт: `GET /api/v1/experiments/{experiment_id}/report?start=2026-02-01&end=2026-02-15`.  
    Ожидаемо: **200**, в теле `variants` с метриками по вариантам, `metrics` содержат выбранные метрики эксперимента.

**Ожидаемый результат:** все шаги возвращают указанные коды; отчёт показывает данные по вариантам и метрикам.

---

### 1.2 Детерминизм выдачи для одного субъекта

**Цель:** при повторных вызовах decide для одного subject_id и того же флага возвращается один и тот же вариант.

**Шаги:**

1. Вызвать `POST /api/v1/decide` с `{"subject_id": "sub-fixed", "attributes": {}, "flags": ["test_feature_flag"]}` дважды (при активном эксперименте на флаге).

**Ожидаемый результат:** оба ответа содержат одинаковый `flag_value` и один и тот же `decision_id` (или повторное использование существующего решения).

---

### 1.3 Отчёт в разрезе вариантов

**Цель:** в отчёте есть разрез по вариантам и значения выбранных метрик.

**Шаги:**

1. Иметь эксперимент в статусе running с вариантами и хотя бы одним принятым событием (как в 1.1).
2. `GET /api/v1/experiments/{id}/report?start=2026-02-01&end=2026-02-15`.

**Ожидаемый результат:** **200**, в теле есть `variants` (каждый с `variant_id`, `variant_name`, `metric_values`, `event_counts`) и `metrics` с ключами метрик эксперимента.

---

## 2. Негативные сценарии

### 2.1 Неверный логин

**Шаги:**  
`POST /api/v1/auth` с `{"email": "admin@test.com", "password": "wrong"}`.

**Ожидаемый результат:** **401** (или **400**), без выдачи токена.

---

### 2.2 Viewer не может создавать эксперименты

**Шаги:**  
С токеном viewer выполнить `POST /api/v1/experiments` с валидным телом (как в 1.1).

**Ожидаемый результат:** **403**.

---

### 2.3 Невалидное тело запроса (events)

**Шаги:**  
`POST /api/v1/events` с телом, где в событии обязательное поле отсутствует, например нет `decision_id` или `event_type_key`:

```json
{"events": [{"event_id": "e1", "subject_id": "u1", "timestamp": "2026-02-14T12:00:00Z"}]}
```

**Ожидаемый результат:** **200** с телом, в котором принятые события не содержат это событие, а в `rejected` или `errors` указана причина (отсутствие обязательных полей).

---

### 2.4 Неверный тип поля в событии

**Шаги:**  
Отправить событие с типом события, у которого в `required_params` указан числовой параметр, а в событии передать строку (или наоборот).

**Ожидаемый результат:** событие отклонено, в ответе указана ошибка валидации (например **200** с полем `rejected`/`errors`).

---

### 2.5 Дубликат события (идемпотентность)

**Шаги:**  
Отправить одно и то же событие (тот же `event_id`, `decision_id`, `event_type_key`, `subject_id`, `timestamp`) дважды через `POST /api/v1/events`.

**Ожидаемый результат:** первый запрос принимает событие; второй не меняет итоговый учёт (дубликат не увеличивает счётчики). В ответе второе отправление может быть помечено как дубликат/игнор.

---

### 2.6 Недопустимый переход статуса эксперимента

**Шаги:**  
Для эксперимента в статусе `draft` вызвать `PATCH /api/v1/experiments/{id}/status` с `{"new_status": "running"}` (переход draft → running без ревью запрещён).

**Ожидаемый результат:** **400** (или **409**), статус остаётся `draft`.

---

### 2.7 Запуск без достаточных одобрений

**Шаги:**  
Перевести эксперимент в `on_review`, не выполняя одобрений (или меньше чем `min_approvals`). Попытаться перевести в `running`.

**Ожидаемый результат:** переход в `running` возможен только из `approved`; пока одобрений недостаточно, статус остаётся `on_review`.

---

## 3. Граничные сценарии

### 3.1 Decide при отсутствии активного эксперимента (default)

**Цель:** для флага без активного эксперимента возвращается `default_value` флага.

**Шаги:**  
Использовать флаг, для которого нет эксперимента в статусе running/paused (или новый флаг без экспериментов).  
`POST /api/v1/decide` с `{"subject_id": "u99", "attributes": {}, "flags": ["<flag_key>"]}` (ключ флага).

**Ожидаемый результат:** **200**, в `flags` элемент с `flag_value` равным `default_value` флага, без привязки к эксперименту (или `experiment_id: null`).

---

### 3.2 Субъект вне таргетинга

**Цель:** при таргетинге, исключающем субъекта, пользователь не попадает в эксперимент и получает default.

**Шаги:**  
Создать эксперимент с `targeting_rule`, который для части субъектов возвращает false (например, по атрибуту). Вызвать decide с `attributes`, не проходящими правило.

**Ожидаемый результат:** **200**, в решении `flag_value` = `default_value` флага, эксперимент не назначен.

---

### 3.3 Отчёт с пустым окном дат

**Шаги:**  
`GET /api/v1/experiments/{id}/report?start=2030-01-01&end=2030-01-02` (период, в котором нет событий).

**Ожидаемый результат:** **200**, отчёт с нулевыми или пустыми значениями по вариантам в этом окне.

---

### 3.4 Конверсия без предшествующей экспозиции (зависимость типов событий)

**Цель:** тип события `demo_conversion` зависит от `demo_exposure`; конверсия без экспозиции по тому же decision_id не должна учитываться как успешная конверсия в метриках, зависящих от порядка.

**Шаги:**  
Получить `decision_id` из decide. Отправить только событие с `event_type_key": "demo_conversion"` для этого `decision_id`, не отправляя `demo_exposure`.

**Ожидаемый результат:** событие может быть принято (200), но в логике атрибуции/метрик конверсия без экспозиции обрабатывается согласно правилам (например, отложенная очередь или неучёт в метрике). Поведение проверяется по отчёту или по документации к `requires_show_event_type_id`.

---

## 4. Доп. фича: Learnings Library

### 4.1 Заполнение learning и проверка похожих кейсов

**Цель:** зафиксировать выводы по эксперименту и получить список похожих кейсов перед новым запуском.

**Шаги:**

1. Иметь созданный эксперимент (`exp_id`) и токен experimenter-владельца.
2. Заполнить learning:
   `PUT /api/v1/experiments/{exp_id}/learning` с телом:
   ```json
   {
     "hypothesis": "Новый вариант выдачи ускорит поиск",
     "primary_metric_key": "conversion_rate",
     "result_outcome": "no_effect",
     "result_action": "repeat",
     "targeting_summary": "web, RU, новые пользователи",
     "platforms": ["web"],
     "countries": ["RU"],
     "app_versions": ["web-2026.02"],
     "product_tags": ["search", "ranking"],
     "change_type": "search_algorithm",
     "variant_structure": {"kind": "ab", "weights": [0.5, 0.5]},
     "notes": "Эффекта по primary нет, guardrail стабильный",
     "is_completed": true,
     "guardrails": [{"metric_key": "latency_p95", "threshold_value": 500, "trigger_count": 0}]
   }
   ```
3. Проверить запись:
   `GET /api/v1/experiments/{exp_id}/learning` и `GET /api/v1/learnings/{learning_id}`.
4. Найти похожие:
   `GET /api/v1/learnings/{learning_id}/similar?limit=5`.
5. Посмотреть аудит:
   `GET /api/v1/learnings/{learning_id}/audit`.

**Ожидаемый результат:** learning сохранён, в `similar` возвращаются похожие кейсы с `score` и `reasons`, в `audit` есть история изменений learning и guardrails.

---

## Связь с тестами и критериями

| Сценарий | Тесты / критерий |
|----------|-------------------|
| 1.1 Сквозной путь | `backend/README.md` демо; B1-5; test_decide_api, test_events_api, test_reports_api |
| 1.2 Детерминизм | B2-4; `test_decide_same_subject_same_value` |
| 1.3 Отчёт по вариантам | B6-2; test_reports_api |
| 2.1 Неверный логин | test_auth_login_invalid_* |
| 2.2 Viewer 403 | test_users_api / права |
| 2.3–2.4 События | B4-1, B4-2; test_events_submit_required_params_rejected, test_events_submit_invalid_* |
| 2.5 Дубликаты | B4-3; test_events_submit_batch_mixed_accepted_rejected_duplicates |
| 2.6–2.7 Статусы | B3-3, B3-4; test_experiments_api (переходы статусов) |
| 3.1 Default без эксперимента | B2-1; test_decide_returns_default_value_when_no_experiment |
| 3.2 Таргетинг | B2-2; тесты decide с targeting_rule |
| 3.3 Пустое окно отчёта | test_report_* (период) |
| 3.4 Зависимость событий | B4-5; event types requires_show, events_submit |
| 4.1 Learnings library | tests/test_learnings_api.py; FX-1/FX-2 (доп. фича п.9) |

Данные для автоматических тестов создаются сидом `tests/seed_test_data.py` и при необходимости фикстурами в `tests/conftest.py` (например, уникальные флаги/эксперименты на тест).
