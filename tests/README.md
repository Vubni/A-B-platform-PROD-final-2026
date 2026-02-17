# API-тесты

Тесты проверяют API по контракту Swagger: health, ready, metrics, **auth**, **users (профили)**, **feature flags**, **experiments**.

## Структура

- `conftest.py` — фикстуры (base_url, сессия, токены admin/experimenter, flag_id).
- `test_health.py` — `/health`, `/ready`, `/metrics`.
- `test_experiments_api.py` — эксперименты (CRUD, статусы, варианты, guardrail-history).
- `test_flags_api.py` — флаги (список, get по ключу, создание, обновление default_value).
- `test_users_api.py` — авторизация и пользователи/профили (список, get, создание, обновление).
- `test_decide_api.py` — Runtime Decide: 401 без токена, 403 для admin/experimenter, 200 для viewer, валидация 422/404; возврат default_value без эксперимента, консистентность для одного subject_id, порядок ответа как в запросе, доля аудитории ~20%.

Сид данных для тестов выполняется скриптом `tests/seed_test_data.py` (пользователи admin@test.com, experimenter@test.com, viewer@test.com, approver@test.com и флаг test_feature_flag).

## Предусловия

- Запущены `postgres` и `backend` (например, `docker-compose up -d postgres backend`).
- Выполнено сидирование (при запуске через Docker — делается автоматически в контейнере `tests`).

## Запуск

### Локально

Из корня проекта:

```bash
pip install -r backend/requirements.txt -r requirements-test.txt
export API_BASE_URL=http://localhost:80
python tests/seed_test_data.py
pytest
```

Или если backend уже поднят и сид выполнен ранее:

```bash
export API_BASE_URL=http://localhost:80
pytest
```

### Через Docker (из корня проекта)

```bash
docker-compose --profile test run --rm --build tests
```

Поднимет при необходимости postgres и backend, выполнит сидирование и запустит pytest для каталога `tests/`.

### Отдельные модули

```bash
pytest tests/test_health.py
pytest tests/test_flags_api.py
pytest tests/test_users_api.py
pytest tests/test_experiments_api.py -k "create_success"
pytest tests/test_decide_api.py
```

## Переменные окружения

| Переменная     | Описание                    | По умолчанию           |
|----------------|-----------------------------|------------------------|
| `API_BASE_URL` | Базовый URL API (без `/`)  | `http://localhost:80`  |

Для сидирования в контейнере тестов используются `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (заданы в docker-compose).
