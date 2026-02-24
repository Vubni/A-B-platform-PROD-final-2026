# Backend

Этот каталог содержит backend-сервис LOTTY A/B Platform — решение для задачи PROD 2026.

- **Точка входа**: `server.py`  
- **Фреймворк и стек**: `aiohttp` + PostgreSQL  
- **API и доменная логика**: HTTP-ручки лежат в `api/`, бизнес-логика — в `functions/`, работа с БД — в `database/`.

Полная документация по конфигурации, API, архитектуре, ограничениям и сценариям запуска находится в корневом `README.md` репозитория.

## Переменные конфигурации (`config.py` и env)

Переменные задаются через окружение (`.env` или env). Значения по умолчанию указаны в `config.py`.

### База данных

| Переменная | Env | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `DATE_BASE_CONNECT["host"]` | `DB_HOST` | `0.0.0.0` | Хост PostgreSQL |
| `DATE_BASE_CONNECT["user"]` | `DB_USER` | `user` | Пользователь БД |
| `DATE_BASE_CONNECT["password"]` | `DB_PASSWORD` | — | Пароль БД (обязательно задать в prod) |
| `DATE_BASE_CONNECT["database"]` | `DB_NAME` | `prod` | Имя базы данных |

Для корректной работы триггеров схемы (`docker/postgres/01-init.sql` и `schema/*.sql`) требуется **PostgreSQL 14+** (в 11–13 используется `EXECUTE PROCEDURE` вместо `EXECUTE FUNCTION`). Подробнее — Runbook, раздел «База данных и триггеры».

### Аутентификация и безопасность

| Переменная | Env | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `SECRET` | `RANDOM_SECRET` | `AJd27GqoS#gvxp@V` | Секрет для подписи JWT/сессий; в prod задать свой |
| `AUTH_TOKEN_EXPIRATION` | — | `86400` (24 ч) | Время жизни токена в секундах (константа в коде) |
| — | `SEED_DEMO_USERS` | `1` в docker-compose | Если задана (например `1`), при старте создаются тестовые пользователи, группа аппруверов, флаг `test_feature_flag`, типы событий `demo_*` и метрики — проверка возможна только через Docker и curl, без запуска Python. Для релиза можно отключить в docker-compose. |

### Эксперименты и события

| Переменная | Env | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT` | `MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT` | `2` | Максимум одновременных экспериментов на одного субъекта (subject_id) |
| `EXPERIMENT_COOLDOWN_SECONDS` | `EXPERIMENT_COOLDOWN_SECONDS` | `604800` (7 сут) | Пауза в секундах перед повторным попаданием субъекта в эксперимент по тому же флагу |
| `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` | `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` | `7` | Максимальная задержка в днях: события старше этого срока не привязываются к решению (decision) |
| `LEARNINGS_REQUIRED_ON_COMPLETE` | `LEARNINGS_REQUIRED_ON_COMPLETE` | `false` | Если `true`, завершение эксперимента (`POST .../complete`) разрешено только при наличии заполненного learning (`is_completed=true`) |

### Логирование

Логи выводятся в **структурированном формате** (одна строка JSON на событие). Формат полей и примеры — в [Runbook: Наблюдаемость и логи](docs/Runbook.md#наблюдаемость-и-логи-b9-4).

| Переменная | Env | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `LOG_DIR` | — | `logs` | Каталог для файлов логов |
| `LOG_MAX_BYTES` | — | `10485760` (10 МБ) | Размер одного лог-файла до ротации (в байтах) |
| `LOG_BACKUP_COUNT` | — | `3` | Сколько ротированных файлов хранить |

---

## API

Префикс API: `/api/v1`. Swagger UI: `http://localhost/`

| Группа | Метод | Путь |
|--------|-------|------|
| **Health** | GET | `/health`, `/ready`, `/metrics` |
| **Auth** | POST | `/api/v1/auth` |
| **Users** | GET, POST | `/api/v1/users` |
| | GET, PATCH | `/api/v1/users/{id}` |
| **Approver groups** | GET, POST | `/api/v1/approver-groups` |
| | PATCH | `/api/v1/approver-groups/{id}` |
| **Feature flags** | POST, GET | `/api/v1/flags` |
| | GET, PATCH | `/api/v1/flags/{key}` |
| **Experiments** | POST, GET | `/api/v1/experiments` |
| | GET, PATCH | `/api/v1/experiments/{id}` |
| | PATCH | `/api/v1/experiments/{id}/status` |
| | POST | `/api/v1/experiments/{id}/complete` |
| | POST | `/api/v1/experiments/{id}/archive` |
| | POST | `/api/v1/experiments/{id}/variants` |
| | PATCH | `/api/v1/experiments/{id}/variants/{variant_id}` |
| | DELETE | `/api/v1/experiments/{id}/variants/{variant_id}` |
| | GET | `/api/v1/experiments/{id}/guardrail-history` |
| **Guardrails** | GET | `/api/v1/guardrails` |
| | GET | `/api/v1/guardrails/{metric_key}` |
| | POST | `/api/v1/guardrails` |
| | DELETE | `/api/v1/guardrails/{metric_key}` |
| **Decide** | POST | `/api/v1/decide` |
| **Events** | POST | `/api/v1/events` |
| **Event types** | GET, POST | `/api/v1/event-types` |
| | GET, PATCH, DELETE | `/api/v1/event-types/{id}` |
| **Reports** | GET | `/api/v1/experiments/{id}/report` |
| **Learnings** | GET | `/api/v1/learnings` |
| | GET | `/api/v1/learnings/{id}` |
| | GET | `/api/v1/learnings/{id}/audit` |
| | GET | `/api/v1/learnings/{id}/similar` |
| | GET | `/api/v1/experiments/{id}/learning` |
| | PUT | `/api/v1/experiments/{id}/learning` |
| **Metrics** | GET, POST | `/api/v1/metrics` |
| | GET, PATCH | `/api/v1/metrics/{key}` |

## Демо-сценарий (happy-path)

1. **Создать флаг** (если ещё нет):
   ```bash
   curl -X POST http://localhost/api/v1/flags \
     -H "Content-Type: application/json" \
     -d '{"key": "button_color", "value_type": "string", "default_value": "green"}'
   ```

2. **Создать и запустить эксперимент**: создать эксперимент с вариантами A/B, отправить на ревью, одобрить, запустить.

3. **Выдача варианта** (в `flags` передавайте **ключи флагов**, например `"button_color"`):
   ```bash
   curl -X POST http://localhost/api/v1/decide \
     -H "Content-Type: application/json" \
     -d '{"subject_id": "u42", "attributes": {}, "flags": ["button_color"]}'
   ```
   В ответе — `flags` (массив решений) и для каждого флага **`decision_id`** для привязки событий (выдаётся всегда, в т.ч. при отсутствии эксперимента или при default).

4. **Событие** (в каждом элементе массива `events` указывайте **event_type_key** — ключ типа события из каталога `GET /api/v1/event-types`):
   ```bash
   curl -X POST http://localhost/api/v1/events \
     -H "Content-Type: application/json" \
     -d '{"events": [{"event_id": "ev-1", "decision_id": "<из шага 3>", "event_type_key": "exposure", "subject_id": "u42", "timestamp": "2026-02-14T12:00:00Z"}]}'
   ```

5. **Отчёт по эксперименту**:
   ```bash
   curl "http://localhost/api/v1/experiments/{experiment_id}/report?start=2026-02-01&end=2026-02-15"
   ```

**Тестовые данные.** При запуске через Docker (`docker compose up -d`) с `SEED_DEMO_USERS=1` типы событий `demo_exposure`, `demo_click`, `demo_conversion` и метрики `demo_impressions`, `demo_conversions`, `demo_conversion_rate` создаются при старте автоматически — ничего дополнительно запускать не нужно. Для локального запуска без Docker: `python tests/seed_test_data.py`.

**Полные сценарии.** Пошаговые сценарии (happy-path, негативные, граничные) с ожидаемыми результатами — в **`backend/docs/demo-scenarios.md`**. Для проверяющего: **`backend/docs/reviewer-test-guide.md`** — тестовые пользователи, токены, UUID флага и готовый сквозной сценарий «выдача варианта → событие → отчёт» через curl после `docker compose up -d`.

## Роли и аппрувер-группы

| Роль | Права |
|------|-------|
| **Admin** | Управление пользователями и ролями, настройка правил ревью |
| **Experimenter** | Создание экспериментов, отправка на ревью |
| **Approver** | Одобрение/отклонение экспериментов в своей группе |
| **Viewer** | Только чтение |

## Жизненный цикл эксперимента

Состояния и действия соответствуют диаграмме из ТЗ (состояние `on_review` эквивалентно `in_review`):

- **draft** — черновик, можно редактировать параметры, таргетинг, варианты и метрики.
  - Переход: `draft → on_review` — отправка на ревью (`PATCH /experiments/{id}/status` с `status="on_review"`), только владельцем‑experimenter.
- **on_review** — на ревью, решения принимают только аппруверы (с учётом approver-групп и fallback-политики).
  - Переходы: `on_review → approved | rejected | draft` — действия ревью (`status="approved" | "rejected" | "draft"`), каждое действие записывается в историю ревью.
- **approved** — одобрен, готов к запуску.
  - Переход: `approved → running` — запуск (`status="running"`), только владельцем‑experimenter; дополнительно соблюдается инвариант «один активный эксперимент на флаг».
- **running / paused** — запущен / на паузе.
  - Переходы: `running ↔ paused` — пауза/возобновление (`status="paused"` / `status="running"`).
  - Завершение: `POST /experiments/{id}/complete` с `completion_outcome = rollout_winner | rollback | no_effect` переводит эксперимент в состояние **completed** и фиксирует исход + комментарий.
- **completed** — эксперимент завершён, решение принято.
  - Переход: `completed → archived` — архивирование через `POST /experiments/{id}/archive` (только владелец‑experimenter).
- **rejected** — отклонён; для повторного запуска требуется доработка: при любом изменении через `PATCH /experiments/{id}` статус автоматически переводится в `draft`, после чего эксперимент можно снова отправить на ревью.
- **archived** — архив; эксперимент только для чтения, параметры не меняются.

Матрица состояний эксперимента:

| From        | To          | Как переводится                                             | Кто может                           | Комментарий                                                                 |
|------------|-------------|-------------------------------------------------------------|-------------------------------------|------------------------------------------------------------------------------|
| draft      | on_review   | PATCH `/experiments/{id}/status` с `status="on_review"`     | experimenter‑владелец               | Проверяются базовые инварианты (варианты, веса, audience_fraction и т.п.).  |
| on_review  | approved    | PATCH `/experiments/{id}/status` с `status="approved"`      | approver (с правом доступа к эксперименту) | Учитывается approver‑группа и `min_approvals`.                              |
| on_review  | rejected    | PATCH `/experiments/{id}/status` с `status="rejected"`      | approver                            | Окончательное решение по текущей конфигурации; для новой попытки конфигурацию нужно изменить (PATCH переведёт статус в draft). |
| on_review  | draft       | PATCH `/experiments/{id}/status` с `status="draft"`         | approver                            | «Запрос правок» (requested_changes): откат на draft для доработки.          |
| approved   | running     | PATCH `/experiments/{id}/status` с `status="running"`       | experimenter‑владелец               | Гарантируется один `running/paused` эксперимент на флаг.                    |
| running    | paused      | PATCH `/experiments/{id}/status` с `status="paused"`        | experimenter‑владелец               | Временная остановка эксперимента.                                           |
| paused     | running     | PATCH `/experiments/{id}/status` с `status="running"`       | experimenter‑владелец               | Возобновление эксперимента.                                                 |
| running    | completed   | POST `/experiments/{id}/complete`                           | experimenter‑владелец               | `completion_outcome = rollout_winner / rollback / no_effect`.               |
| paused     | completed   | POST `/experiments/{id}/complete`                           | experimenter‑владелец               | Аналогично: завершение из paused.                                           |
| completed  | archived    | POST `/experiments/{id}/archive`                            | experimenter‑владелец               | Перевод в архив, только из `completed`.                                     |
| rejected   | —           | —                                                           | —                                   | Прямых переходов нет; изменение эксперимента (PATCH) переводит его в draft. |
| archived   | —           | —                                                           | —                                   | Терминальное состояние, только чтение.                                      |

Параметры, влияющие на раздачу (доля аудитории, таргетинг, варианты, метрики), после первого запуска считаются «замороженными»: в статусах `running` / `paused` / `completed` / `archived` API возвращает ошибку при попытке изменить эти поля (см. сообщение `"Experiment is frozen after start; only 'name' can be updated"`).

**Fallback аппрувер-группы (сценарий без явной группы):** сначала персональная группа (`approver_groups.experimenter_id = <id>`), затем дефолтная группа (`experimenter_id IS NULL` через POST/PATCH `/api/v1/approver-groups`). Если ни одной нет — **fallback**: одобрять могут все пользователи с ролью `approver` и `admin` в системе; минимальный порог одобрений = `max(1, ceil(N × FALLBACK_APPROVAL_PERCENT))`, где N — число таких пользователей. Процент задаётся в `config.py` (`FALLBACK_APPROVAL_PERCENT`, по умолчанию `0.6`).

## Ключевые архитектурные решения (B7-4)

1. **Моно-сервисный backend на aiohttp + PostgreSQL**  
   - **Решение**: единый backend-сервис (`backend/server.py`) без внутренних микросервисов; одна БД PostgreSQL (`docker/postgres/`).  
   - **Причины**: снизить сложность реализации для олимпиады, упростить отладку и демонстрацию end-to-end сценариев.  
   - **Риски/ограничения**: масштабирование по доменам потребует рефакторинга (выделение сервисов), все горячие пути завязаны на одну БД.

2. **Жёсткие инварианты и бизнес-правила на уровне БД**  
   - **Решение**: ключевые ограничения зафиксированы в схеме и триггерах: один активный эксперимент на флаг (`idx_experiments_one_active_per_flag`), ровно один control-вариант и сумма весов, равная `audience_fraction` (триггер `check_experiment_variants_invariants`), запрет изменения таргетинга/вариантов в статусах `running`/`paused` (триггеры `check_experiment_frozen_params`, `check_experiment_variants_frozen`).  
   - **Причины**: защита от логических ошибок на уровне приложения, единые гарантии для всех путей обновления.  
   - **Риски/ограничения**: изменение бизнес-логики требует правок в SQL-функциях; миграции схемы становятся сложнее.

3. **Атрибуция конверсий только через `decision_id` и типы событий**  
   - **Решение**: все события (`event_occurrences`) ссылаются на `decisions.decision_id`; типы событий (`event_types`) описывают обязательные параметры и зависимости (`requires_show_event_type_id`), а для зависимых событий используется очередь `events_dependency_queue`, которая позволяет принимать конверсии раньше экспозиции (out-of-order) в пределах окна.  
   - **Причины**: единый способ связать экспозицию и конверсию; отчёты и guardrail-метрики опираются только на подтверждённые решения и события, связанные с конкретными решениями.  
   - **Риски/ограничения**: «сырые» события без `decision_id` не учитываются; поздние конверсии за пределами окна `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` (по умолчанию 7 дней) не будут привязаны к решению и игнорируются в отчётах.

4. **Гибкий каталог метрик с декларативными правилами агрегации**  
   - **Решение**: каталог метрик (`metric_catalog`) хранит `aggregation_rule` (count_events, avg, percentile, ratio), `attribution_rule`, `event_expectations`; расчёт реализован в `backend/functions/reports.py`.  
   - **Причины**: добавление новых метрик без изменения схемы БД экспериментов; переиспользование в отчётах и guardrail-правилах.  
   - **Риски/ограничения**: набор поддерживаемых агрегирующих правил фиксирован; сложные метрики (когорты, retention) не поддержаны.

5. **Guardrail-метрики как отдельный слой над каталогом метрик**  
   - **Решение**: guardrail-правила (`metric_guardrails`, `experiment_metrics.metric_type = 'guardrail'`) используют тот же каталог метрик; проверка и действия реализованы в `backend/functions/guardrails.py`.  
   - **Причины**: единая точка правды по расчёту метрик, повторное использование для отчётов и safety.  
   - **Риски/ограничения**: ошибки в правилах агрегации одновременно влияют и на отчёты, и на guardrail; действия guardrail завязаны на текущую модель статусов эксперимента.

6. **Прозрачная граница «HTTP API ↔ бизнес-логика»**  
   - **Решение**: модули `backend/api/*` содержат только HTTP-аспекты (валидация, авторизация, сериализация), доменная логика вынесена в `backend/functions/*`.  
   - **Причины**: удобнее тестировать, проще читать и переиспользовать доменные функции; можно заменить web-фреймворк с минимальными изменениями.  
   - **Риски/ограничения**: возможна частичная дублирующая валидация (pydantic + проверки на уровне функций).

## Ограничения и упрощения (B7-9)

1. **Одна БД PostgreSQL, без шардирования и реплик**  
   - **Где в коде**: `docker/postgres/schema/`, `backend/database/database.py`.  
   - **Как проявляется**: все операции чтения/записи (решения, события, отчёты) проходят через одну БД; в демо нет сценариев с распределённым хранилищем.  
   - **Риск**: при росте нагрузки одна БД становится bottleneck; для прод-подхода потребуется шардинг или реплики.

2. **Нет UI/админки — только HTTP API и Swagger**  
   - **Где в коде**: `backend/api/*`, описание маршрутов в `backend/server.py`.  
   - **Как проявляется**: все сценарии выполняются через curl/HTTP-клиент или Swagger UI; нет UX для прод-пользователей.  
   - **Риск**: для прома нужна отдельная админка поверх API.

3. **Ограниченный набор типов метрик и правил агрегации**  
   - **Где в коде**: `backend/functions/reports.py::_compute_metric_value`, таблица `metric_catalog`.  
   - **Как проявляется**: поддерживаются только `count_events`, `avg`, `percentile`, `ratio`; сложные метрики (когорты, retention) не реализованы.  
   - **Риск**: расширение набора метрик требует доработки кода, а не только данных в каталоге.

4. **Атрибуция только по `decision_id` и окну по времени**  
   - **Где в коде**: `backend/functions/events_submit.py`, `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` в `config.py`.  
   - **Как проявляется**: события без валидного `decision_id` или старше окна не атрибутируются к эксперименту.  
   - **Риск**: поздние конверсии и «висячие» события игнорируются; окно атрибуции нужно подбирать под продукт.

5. **Приём событий: синхронно по умолчанию, с опциональной очередью Kafka**  
   - **Где в коде**: `backend/api/events.py` → `backend/functions/events_submit.py`, опционально `backend/kafka_events.py`; переключатель — `EVENTS_USE_KAFKA` и `KAFKA_BOOTSTRAP_SERVERS` в `config.py`.  
   - **Как проявляется**: по умолчанию (`EVENTS_USE_KAFKA=false`) `POST /api/v1/events` валидирует батч и сразу пишет события в БД. При включённой Kafka валидные батчи без ошибок валидации кладутся в топик `KAFKA_EVENTS_TOPIC` с ответом `202 Accepted`, а частично невалидные батчи всегда обрабатываются синхронно через `process_events_batch` с подсчётом `accepted/duplicates/rejected`.  
   - **Риск**: при синхронном режиме всплески нагрузки могут замедлить API; при режиме с Kafka появляется задержка между приёмом события и фактической записью в БД, поэтому важно следить за здоровьем брокера и lag потребителей (см. Runbook про нагрузку и очереди).

6. **Фиксированная модель ролей и ревью**  
   - **Где в коде**: `docker/postgres/schema/` (`user_role`, `approver_groups`), `backend/api/users.py`, `backend/functions/experiments.py` (ревью).  
   - **Как проявляется**: роли `admin`, `experimenter`, `approver`, `viewer`; правила ревью привязаны к approver-группам и `min_approvals`.  
   - **Риск**: многоуровневые схемы ревью и внешние аппруверы потребуют изменения схемы и логики.

7. **Отчёты без сложной динамики и доверительных интервалов**  
   - **Где в коде**: `backend/functions/reports.py::get_experiment_report`.  
   - **Как проявляется**: отчёт возвращает агрегации за окно и сводку по основной метрике; поле `dynamics` заполняется упрощённо одним агрегатом по всему окну (без разбиения по подинтервалам и без доверительных интервалов).  
   - **Риск**: для прод-сценариев потребуется детализация по времени, доверительные интервалы и визуализация.

## Карта репозитория (B7-8)

Репозиторий разбит по слоям: API (эндпоинты), бизнес-логика, доступ к данным и инфраструктура.

```text
.
├── .github/
│   └── workflows/
│       └── lint.yml         # CI: линтинг и проверка форматирования (Ruff)
├── backend/
│   ├── api/                 # HTTP-эндпоинты (aiohttp handlers, валидация, auth)
│   │   ├── auth.py          # Логин, выдача JWT
│   │   ├── users.py         # Пользователи, роли, approver-группы
│   │   ├── flags.py         # CRUD по feature flags
│   │   ├── experiments.py   # CRUD + статусы экспериментов, ревью, guardrail-history
│   │   ├── decide.py        # Runtime-решения по флагам (POST /api/v1/decide)
│   │   ├── events.py        # Типы событий и приём батчей событий (POST /api/v1/events)
│   │   ├── reports.py       # Отчёты по экспериментам, каталог метрик
│   │   ├── guardrails.py    # CRUD по настройкам guardrail-метрик
│   │   ├── health.py        # /health и /ready
│   │   ├── system_metrics.py# /metrics и middleware для счётчиков
│   │   ├── validate.py      # Общая валидация запросов (pydantic и др.)
│   │   └── get_file.py      # Раздача статики (Swagger UI и т.п.)
│   ├── functions/           # Бизнес-логика (без HTTP)
│   │   ├── decide.py        # Алгоритм выдачи вариантов и записи decisions
│   │   ├── events_submit.py # Валидация, дедупликация, атрибуция событий
│   │   ├── events_dependency_queue.py # Очередь зависимостей событий (show → conversion)
│   │   ├── experiments.py   # Жизненный цикл экспериментов, ревью, guardrail-history
│   │   ├── reports.py       # Расчёт метрик и отчёта по эксперименту
│   │   ├── guardrails.py    # Проверка guardrail-метрик и автоматический pause/rollback
│   │   ├── metrics.py       # Каталог метрик и правила агрегации
│   │   ├── event_types.py   # Каталог типов событий
│   │   ├── flags.py         # CRUD и логика feature flags
│   │   └── users.py         # Пользователи, роли, approver-группы (доменная логика)
│   ├── database/
│   │   ├── database.py      # Обёртка над async-подключением к PostgreSQL
│   │   └── functions.py     # Инициализация справочных данных
│   ├── docs/                # Документация и схемы для Swagger
│   │   ├── schems.py        # Модели/схемы для OpenAPI (Swagger)
│   │   ├── compliance-matrix.md  # Матрица трассируемости задание–критерий–реализация
│   │   └── c4-diagrams.md   # C4-диаграммы (Context, Container, Component)
│   ├── config.py            # Конфигурация, переменные окружения, настройка логгера
│   ├── core.py              # Общие утилиты: авторизация (JWT), проверка прав, константы
│   ├── dsl.py               # Парсер правил таргетинга (выражения, операторы, даты)
│   ├── server.py            # Точка входа backend, регистрация маршрутов и middleware
│   ├── Runbook.md           # Операционный runbook (логи, нагрузка, линт/формат)
│   └── requirements*.txt    # Зависимости backend
├── docker/
│   └── postgres/
│       ├── 01-init.sql      # Точка входа схемы (подключает schema/*.sql)
│       ├── 02-learnings_library.sql
│       └── schema/          # Схема БД: таблицы, индексы, триггеры
├── tests/                   # Интеграционные тесты к HTTP-API
│   ├── conftest.py          # Фикстуры (логин, сиды, base_url)
│   ├── test_*.py            # Наборы тестов по доменным областям
│   ├── requirements-test.txt # Зависимости для запуска тестов
│   └── README.md            # Инструкция по запуску тестов и отчёту о покрытии
├── docker-compose.yml       # Композиция postgres, backend и контейнера с тестами
├── Dockerfile.tests         # Образ для запуска тестов в CI/локально
├── Makefile                 # Цели: lint, format, format-check, install-dev
├── pyproject.toml           # Настройки Ruff (линтинг и форматирование)
└── README.md                # Общий README задачи и требования к запуску
```

**Критичный поток `decide → event → report/guardrail`:**

- **Решение (decide)**:
  - Эндпоинт: `POST /api/v1/decide` (`backend/api/decide.py`).
  - Бизнес-логика: `backend/functions/decide.py` — выбор варианта, запись в таблицу `decisions`.
- **Событие (event)**:
  - Эндпоинт: `POST /api/v1/events` (`backend/api/events.py`).
  - Бизнес-логика: `backend/functions/events_submit.py` — валидация, дедупликация, связь с `decision_id`, зависимые события.
- **Отчёты и guardrail**:
  - Отчёт: `GET /api/v1/experiments/{id}/report` (`backend/api/reports.py` + `backend/functions/reports.py`).
  - Guardrail: проверка и действия — `backend/functions/guardrails.py`; история — таблица `experiment_guardrail_history` в `docker/postgres/schema/`.

## Матрица соответствия и C4 (B7-3, B7-5–B7-7)

- **Матрица** трассируемости «задание–критерий–реализация»: `backend/docs/compliance-matrix.md`. При проверке удобно начинать с неё.
- **C4-диаграммы** (Context, Container, Component): `backend/docs/c4-diagrams.md`.
- **Отчёт о соответствии** критериям B1–B10: `backend/docs/compliance-report.md`.

## Инженерная дисциплина (линтинг и форматирование)

Штатные команды (выполнять из **корня репозитория**):

| Действие | Команда |
|----------|---------|
| Линтинг | `ruff check backend` |
| Форматирование | `ruff format backend` |
| Проверка форматирования (CI) | `ruff format --check backend` |

Для удобства те же команды обёрнуты в `Makefile`:

| Действие | Команда |
|----------|---------|
| Установка dev-зависимостей для линтинга | `make install-dev` |
| Линтинг (через Ruff) | `make lint` |
| Форматирование кода | `make format` |
| Проверка форматирования без изменений | `make format-check` |

Все `make`-команды также нужно вызывать из **корня репозитория**.

Конфигурация Ruff — в корневом `pyproject.toml`. Подробнее — раздел [«Инженерная дисциплина»](Runbook.md#инженерная-дисциплина-b10) в Runbook.

## Runbook и наблюдаемость

В [Runbook.md](Runbook.md) описаны:
- **Формат логов** — структурированный JSON, поля, примеры;
- **Нагрузка и рост данных** — лимиты, партиционирование, масштабирование, очереди, поведение при росте;
- **Инженерная дисциплина** — команды линтинга и форматирования (Ruff).

## Запуск

**Через Docker** (из корня проекта):

```bash
docker compose up -d
```

API: `http://localhost:80`. Логи: `backend_logs` volume.

**Без Docker**:

```bash
cd backend
pip install -r requirements.txt
python server.py
```

## Самостоятельность решения
Структура проекта разработана мной и используется в каждом моём проекте, в начале разработки я загружаю свой шаблон и по нему начинаю делать, зависимость от этой структуры можно увидеть во всех моих backend проектах на github: https://github.com/Vubni. Структура можее показаться сгенерированной ИИ, но это прожившая много проектов структура, потерпевшия поправки и идеальная для меня.
Пример:
- https://github.com/Vubni/postupishka
- https://github.com/Vubni/School-hub

Использование ИИ:
```
Важно: **ответственность за весь код в репозитории несёте вы**, включая сгенерированные фрагменты — вы должны понимать, что именно добавляете, уметь объяснить решение и проверять результат (корректность, безопасность, крайние случаи).
```
Это соблюдается, я полностью понимаю всё, что сгенерировал, а именно:

60% Документации - Документацию я прописывал шаблонами и краткими описаниями, красивое форматирование и более подробное описание мне помогали составлять нейросети.

60% тестов - я создавал основы и наброски тестов, для максимального покрытия использовал нейросети, которые на основе моих набросков - расширяли тесты

10-15% в основном скрипте - Я использовал нейросети для составления мелких функций или написания swagger моментами, основной функционал написан мной, нейросети писали маленькие функции для каких-либо проверок, преобразований и тп.


Я считаю это приемлимым процентом, так как нейросети обязательны в использовании в программировании, они помогают ускорить процесс и не сидеть долго на нонотонных задачах, именно так я и использовал (тесты, документация, мелкие функции)


Все скрипты инициализации таблиц в бд (.sql) я составлял сам с помощью pgadmin (создание в интерфейсе и позже копирование команды sql, перенос в файл .sql), нейросеть лишь немного отфоорматировала эти файлы.