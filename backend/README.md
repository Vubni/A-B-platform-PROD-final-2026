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

### Аутентификация и безопасность

| Переменная | Env | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `SECRET` | `RANDOM_SECRET` | `AJd27GqoS#gvxp@V` | Секрет для подписи JWT/сессий; в prod задать свой |
| `AUTH_TOKEN_EXPIRATION` | — | `86400` (24 ч) | Время жизни токена в секундах (константа в коде) |

### Эксперименты и события

| Переменная | Env | По умолчанию | Описание |
|------------|-----|--------------|----------|
| `MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT` | `MAX_ACTIVE_EXPERIMENTS_PER_SUBJECT` | `2` | Максимум одновременных экспериментов на одного субъекта (subject_id) |
| `EXPERIMENT_COOLDOWN_SECONDS` | `EXPERIMENT_COOLDOWN_SECONDS` | `604800` (7 сут) | Пауза в секундах перед повторным попаданием субъекта в эксперимент по тому же флагу |
| `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` | `EVENTS_DEPENDENCY_MAX_DELAY_DAYS` | `7` | Максимальная задержка в днях: события старше этого срока не привязываются к решению (decision) |

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

3. **Выдача варианта**:
   ```bash
   curl -X POST http://localhost/api/v1/decide \
     -H "Content-Type: application/json" \
     -d '{"subject_id": "u42", "attributes": {}, "flag_keys": ["button_color"]}'
   ```
   В ответе — `decisions` и `decision_id` для атрибуции событий.

4. **Событие**:
   ```bash
   curl -X POST http://localhost/api/v1/events \
     -H "Content-Type: application/json" \
     -d '{"events": [{"event_id": "ev-1", "decision_id": "<из шага 3>", "event_type": "exposure", "subject_id": "u42", "timestamp": "2026-02-14T12:00:00Z"}]}'
   ```

5. **Отчёт по эксперименту**:
   ```bash
   curl "http://localhost/api/v1/experiments/{experiment_id}/report?start=2026-02-01&end=2026-02-15"
   ```

## Роли и аппрувер-группы

| Роль | Права |
|------|-------|
| **Admin** | Управление пользователями и ролями, настройка правил ревью |
| **Experimenter** | Создание экспериментов, отправка на ревью |
| **Approver** | Одобрение/отклонение экспериментов в своей группе |
| **Viewer** | Только чтение |

**Fallback аппрувер-группы:** сначала персональная группа (`approver_groups.experimenter_id = <id>`), затем fallback (`experimenter_id IS NULL` через `PUT /api/v1/approver-groups`), иначе `min_approvals = 1`, аппруверы — все admin.

## Инженерная дисциплина (линтинг и форматирование)

Штатные команды (выполнять из **корня репозитория**):

| Действие | Команда |
|----------|---------|
| Линтинг | `ruff check backend` |
| Форматирование | `ruff format backend` |
| Проверка форматирования (CI) | `ruff format --check backend` |

Конфигурация Ruff — в корневом `pyproject.toml`. Подробнее — раздел [«Инженерная дисциплина»](Runbook.md#инженерная-дисциплина-b10) в Runbook.

## Runbook и наблюдаемость

В [Runbook.md](Runbook.md) описаны:
- **Формат логов** — структурированный JSON, поля, примеры;
- **Нагрузка и рост данных** — лимиты, партиционирование, масштабирование, очереди, поведение при росте;
- **Инженерная дисциплина** — команды линтинга и форматирования (Ruff).

## Структура бэкенда

```
backend/
├── api/
├── functions/
├── database/
├── docs/
│   ├── Runbook.md   # Наблюдаемость, логи, нагрузка и рост данных
│   └── schems.py
├── config.py
├── server.py
├── Dockerfile
└── requirements.txt
```

## Запуск

**Через Docker** (из корня проекта):

```bash
docker-compose up -d postgres backend
```

API: `http://localhost:80`. Логи: `backend_logs` volume.

**Без Docker**:

```bash
cd backend
pip install -r requirements.txt
python server.py
```
