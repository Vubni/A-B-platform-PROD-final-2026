# API-тесты

## Запуск

Локально (из корня проекта):

```bash
pip install -r backend/requirements.txt -r tests/requirements-test.txt
export API_BASE_URL=http://localhost:80
python tests/seed_test_data.py
pytest
```

Только pytest (backend и сид уже есть):

```bash
export API_BASE_URL=http://localhost:80
pytest
```

Docker:

```bash
docker-compose --profile test run --rm --build tests
```

В конце прогона выводится отчёт **покрытия эндпоинтов**: список протестированных эндпоинтов и доля от общего числа (в %).

Отдельные модули:

```bash
pytest tests/test_health.py
pytest tests/test_flags_api.py
pytest tests/test_users_api.py
pytest tests/test_experiments_api.py
pytest tests/test_decide_api.py
```

## Переменные

| Переменная     | По умолчанию          |
|----------------|------------------------|
| `API_BASE_URL` | `http://localhost:80`  |

---

## Отчёт по тестированию и покрытию (B8-4)

### Наборы тестов

Основной фокус — интеграционные тесты HTTP API с живым backend и БД PostgreSQL. Все эндпоинты из OpenAPI спецификации покрыты тестами.

- **Health и наблюдаемость**: `tests/test_health.py` — `/health`, `/ready`, `/metrics` (Prometheus).
- **Пользователи и роли**: `tests/test_users_api.py` — логин, CRUD пользователей, права доступа.
- **Группы аппруверов**: `tests/test_approver_groups_api.py` — GET list, POST create, PATCH update; 401/403/404/409.
- **Feature flags**: `tests/test_flags_api.py` — создание/обновление флагов, валидация ключей.
- **Эксперименты**: `tests/test_experiments_api.py` — CRUD, варианты, статусы, POST `.../complete`, guardrail-history.
- **Guardrails**: `tests/test_guardrails_api.py` — GET list, GET by key, POST upsert, DELETE.
- **Решения (decide)**: `tests/test_decide_api.py` — авторизация, детерминизм, default при отсутствии эксперимента, валидация.
- **События**: `tests/test_events_api.py` — CRUD типов событий, POST /events (батчи), дедупликация, guardrail pause.
- **Отчёты**: `tests/test_reports_api.py` — GET report по эксперименту, валидация окна и параметров.
- **Каталог метрик**: `tests/test_metrics_catalog_api.py` — GET list, GET by key, POST create, PATCH update (admin).

Негативные сценарии (400/401/403/404) покрыты в соответствующих тестах (например, `test_events_api.py::test_events_submit_invalid_body_*`, `test_users_api.py::test_auth_login_invalid_*`).

### Покрытие критериев и принцип набора тестов

Тесты выровнены по обязательным критериям (B1–B10): у каждого проверяемого критерия есть хотя бы один воспроизводимый сценарий (интеграционный или единичный). Количество тестов сознательно не раздувается: приоритет — **максимальное покрытие критериев при минимальном наборе**; явно дублирующие сценарии удалены. Юнит-тесты (`test_experiment_validation.py`) дополняют интеграционные там, где нужна быстрая проверка отдельных правил (например, валидация весов вариантов перед отправкой на ревью).

При запуске `pytest` вывод в консоли разбит по секциям (Health, Users, Flags, Experiments, Decide, Events, Reports). В конце выводится **отчёт покрытия эндпоинтов**: список протестированных эндпоинтов (method + path), при необходимости — список непротестированных и итоговый процент покрытия от общего числа эндпоинтов API.

### Команды запуска

Все команды выполняются **из корня репозитория**.

1. Установка зависимостей для backend и тестов:

```bash
pip install -r backend/requirements.txt -r tests/requirements-test.txt
```

2. Запуск инфраструктуры через Docker:

```bash
docker-compose up -d
```

3. Сидинг тестовых данных (пользователи, метрики, типы событий и т.д.):

```bash
export API_BASE_URL=http://localhost:80
python tests/seed_test_data.py
```

4. Запуск тестов:

**Через Docker:**

```bash
docker-compose --profile test run --rm --build tests
```

**Локально** (при уже поднятых backend и БД):

```bash
pytest tests
```

В конце прогона выводится блок «Покрытие эндпоинтов»: протестированные эндпоинты, при наличии — непротестированные, и итог в виде `N/M эндпоинтов — K%`. Список всех эндпоинтов задаётся в `tests/conftest.py` (ALL_ENDPOINTS), список покрытых тестами — TESTED_ENDPOINTS; при добавлении новых маршрутов в API их нужно добавить в ALL_ENDPOINTS и при появлении тестов — в TESTED_ENDPOINTS.

Опционально можно измерять покрытие кода (pytest-cov):

```bash
pip install pytest-cov
pytest tests --cov=backend --cov-report=term-missing:skip-covered --cov-report=xml:coverage.xml
```