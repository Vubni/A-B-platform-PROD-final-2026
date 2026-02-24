# LOTTY A/B Platform — Backend

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

Логи выводятся в **структурированном формате** (одна строка JSON на событие). Формат полей и примеры — в [Runbook: Наблюдаемость и логи](backend/Runbook.md#наблюдаемость-и-логи-b9-4).

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
   - **Решение**: все события (`event_occurrences`) ссылаются на `decisions.decision_id`; типы событий (`event_types`) описывают обязательные параметры и зависимости (`requires_show_event_type_id`).  
   - **Причины**: единый способ связать экспозицию и конверсию; отчёты и guardrail-метрики опираются только на подтверждённые решения.  
   - **Риски/ограничения**: «сырые» события без `decision_id` не учитываются; поздние конверсии за пределами окна могут быть отброшены.

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
   - **Как проявляется**: все операции чтения/записи (решения, события, отчёты) проходят через одну БД; этого достаточно для демонстрационных и учебных сценариев.  
   - **Ограничение**: при росте нагрузки масштабирование можно выполнять стандартными средствами PostgreSQL (реплики, шардирование и т.п.).

2. **Фокус на HTTP API и Swagger вместо отдельной админки**  
   - **Где в коде**: `backend/api/*`, описание маршрутов в `backend/server.py`.  
   - **Как проявляется**: все сценарии выполняются через curl/HTTP‑клиент или Swagger UI, что упрощает проверку и автоматизацию.  

3. **Ограниченный набор типов метрик и правил агрегации**  
   - **Где в коде**: `backend/functions/reports.py::_compute_metric_value`, таблица `metric_catalog`.  
   - **Как проявляется**: поддерживаются `count_events`, `avg`, `percentile`, `ratio`; более сложные варианты (когорты, retention) не используются, чтобы сфокусироваться на основных сценариях.  

4. **Атрибуция только по `decision_id` и окну по времени**  
   - **Где в коде**: `backend/functions/events_submit.py`, `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` в `config.py`.  
   - **Как проявляется**: события без валидного `decision_id` или старше окна намеренно не атрибутируются к эксперименту; окно атрибуции настраивается через конфигурацию.

5. **Синхронная обработка событий по умолчанию**  
   - **Где в коде**: `backend/api/events.py` → `backend/functions/events_submit.py`.  
   - **Как проявляется**: `POST /api/v1/events` пишет события сразу в БД в базовой конфигурации без внешних очередей; в Runbook описана возможность вынести приём в очередь.

6. **Фиксированная модель ролей и ревью**  
   - **Где в коде**: `docker/postgres/schema/` (`user_role`, `approver_groups`), `backend/api/users.py`, `backend/functions/experiments.py` (ревью).  
   - **Как проявляется**: роли `admin`, `experimenter`, `approver`, `viewer`; правила ревью привязаны к approver-группам и `min_approvals`.  

7. **Отчёты без сложной динамики и доверительных интервалов**  
   - **Где в коде**: `backend/functions/reports.py::get_experiment_report`.  
   - **Как проявляется**: отчёт возвращает агрегации за окно и сводку по основной метрике; поле `dynamics` отражает агрегированный результат по выбранному периоду.

## Карта репозитория (B7-8)

Репозиторий разбит по слоям: API (эндпоинты), бизнес-логика, доступ к данным и инфраструктура.

```text
.
├── backend/
│   ├── Dockerfile
│   ├── README.md                 # Краткое описание backend
│   ├── Runbook.md                # Операционный runbook (логи, нагрузка, линт/формат)
│   ├── api/                      # HTTP-эндпоинты (aiohttp handlers, валидация, auth)
│   │   ├── auth.py               # Логин, выдача JWT
│   │   ├── users.py              # Пользователи, роли, approver-группы
│   │   ├── flags.py              # CRUD по feature flags
│   │   ├── experiments.py        # CRUD + статусы экспериментов, ревью, guardrail-history
│   │   ├── decide.py             # Runtime-решения по флагам (POST /api/v1/decide)
│   │   ├── events.py             # Типы событий и приём батчей событий (POST /api/v1/events)
│   │   ├── reports.py            # Отчёты по экспериментам, каталог метрик
│   │   ├── guardrails.py         # CRUD по настройкам guardrail-метрик
│   │   ├── health.py             # /health и /ready
│   │   ├── system_metrics.py     # /metrics и middleware для счётчиков
│   │   ├── validate.py           # Общая валидация запросов (pydantic и др.)
│   │   └── get_file.py           # Раздача статики (Swagger UI и т.п.)
│   ├── autopilot_ramp/           # Логика автопилота и ramp-up экспериментов
│   ├── functions/                # Бизнес-логика (без HTTP)
│   │   ├── decide.py             # Алгоритм выдачи вариантов и записи decisions
│   │   ├── events_submit.py      # Валидация, дедупликация, атрибуция событий
│   │   ├── events_dependency_queue.py # Очередь зависимостей событий (show → conversion)
│   │   ├── experiments.py        # Жизненный цикл экспериментов, ревью, guardrail-history
│   │   ├── reports.py            # Расчёт метрик и отчёта по эксперименту
│   │   ├── guardrails.py         # Проверка guardrail-метрик и автоматический pause/rollback
│   │   ├── metrics.py            # Каталог метрик и правила агрегации
│   │   ├── event_types.py        # Каталог типов событий
│   │   ├── flags.py              # CRUD и логика feature flags
│   │   └── users.py              # Пользователи, роли, approver-группы (доменная логика)
│   ├── database/
│   │   ├── database.py           # Обёртка над async-подключением к PostgreSQL
│   │   └── functions.py          # Инициализация справочных данных
│   ├── docs/                     # Документация и схемы для Swagger и проверки
│   │   ├── schems.py             # Модели/схемы для OpenAPI (Swagger)
│   │   ├── compliance-matrix.md  # Матрица трассируемости задание–критерий–реализация
│   │   ├── c4-diagrams.md        # C4-диаграммы (Context, Container, Component)
│   │   ├── demo-scenarios.md     # Demo-сценарии (happy-path, негативные, граничные)
│   │   └── reviewer-test-guide.md # Гайд для проверяющего (токены, сценарии и т.п.)
│   ├── config.py                 # Конфигурация, переменные окружения, настройка логгера
│   ├── core.py                   # Общие утилиты: авторизация (JWT), проверка прав, константы
│   ├── dsl.py                    # Парсер правил таргетинга (выражения, операторы, даты)
│   ├── kafka_events.py           # Обработка событий из Kafka (если используется)
│   ├── scripts/                  # Вспомогательные скрипты разработки/запуска
│   ├── server.py                 # Точка входа backend, регистрация маршрутов и middleware
│   ├── requirements-dev.txt      # Dev-зависимости для разработки и линтинга
│   └── requirements.txt          # Основные зависимости backend
├── coverage/                     # Локальные отчёты о покрытии
├── docker/
│   └── postgres/
│       ├── 01-init.sql           # Точка входа схемы (подключает schema/*.sql)
│       ├── 02-learnings_library.sql
│       └── schema/               # Схема БД: таблицы, индексы, триггеры
├── logs/                         # Локальные логи (для docker / разработки)
├── tests/                        # Интеграционные тесты к HTTP-API
│   ├── conftest.py               # Фикстуры (логин, сиды, base_url)
│   ├── test_*.py                 # Наборы тестов по доменным областям
│   ├── requirements-test.txt     # Зависимости для запуска тестов
│   ├── seed_test_data.py         # Скрипт сидирования тестовых данных без Docker
│   └── README.md                 # Инструкция по запуску тестов и отчёту о покрытии
├── docker-compose.yml            # Композиция postgres, backend и контейнера с тестами
├── Dockerfile.tests              # Образ для запуска тестов в CI/локально
├── Makefile                      # Цели: lint, format, format-check, install-dev
├── pyproject.toml                # Настройки Ruff (линтинг и форматирование)
├── pytest.ini                    # Конфигурация pytest
├── test.py                       # Вспомогательный скрипт запуска тестов
└── README.md                     # Общий README проекта (этот файл)
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

Конфигурация Ruff — в корневом `pyproject.toml`. Подробнее — раздел [«Инженерная дисциплина»](backend/Runbook.md#инженерная-дисциплина-b10) в Runbook.

## Runbook и наблюдаемость

В [backend/Runbook.md](backend/Runbook.md) описаны:
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

Примеры похожих проектов:
- https://github.com/Vubni/postupishka
- https://github.com/Vubni/School-hub

Использование ИИ:
```
Важно: ответственность за весь код в репозитории несёте вы, включая сгенерированные фрагменты — вы должны понимать, что именно добавляете, уметь объяснить решение и проверять результат (корректность, безопасность, крайние случаи).
```
Это соблюдается, я полностью понимаю всё, что сгенерировал, а именно:

- 60% документации — Документацию я прописывал шаблонами и краткими описаниями, красивое форматирование и более подробное описание мне помогали составлять нейросети.
- 60% тестов — я создавал основы и наброски тестов, для максимального покрытия использовал нейросети, которые на основе моих набросков расширяли тесты.
- 10–15% в основном скрипте — Я использовал нейросети для составления мелких функций или написания Swagger моментами, основной функционал написан мной, нейросети писали маленькие функции для проверок, преобразований и т.п.

Я считаю это приемлемым процентом, так как нейросети обязательны в использовании в программировании, они помогают ускорить процесс и не сидеть долго на монотонных задачах, именно так я их и использовал (тесты, документация, мелкие функции).

Все скрипты инициализации таблиц в БД (`.sql`) я составлял сам с помощью pgAdmin (создание в интерфейсе и позже копирование команды SQL, перенос в файл `.sql`), нейросеть лишь немного отформатировала эти файлы.
