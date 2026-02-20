# API-тесты

## Запуск

Локально (из корня проекта):

```bash
pip install -r backend/requirements.txt -r requirements-test.txt
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

Основной фокус — интеграционные тесты HTTP API с живым backend и БД PostgreSQL.

- **Health и наблюдаемость**: `tests/test_health.py` — `/health`, `/ready`.
- **Пользователи и роли**: `tests/test_users_api.py` — логин, роли, права доступа.
- **Feature flags**: `tests/test_flags_api.py` — создание/обновление флагов, валидация ключей.
- **Эксперименты и ревью**: `tests/test_experiments_api.py` — lifecycle `draft → on_review → approved → running → paused/completed`, ревью, guardrail-history.
- **Решения (decide)**: `tests/test_decide_api.py` — авторизация, детерминизм, `default` при отсутствии эксперимента, валидация UUID флагов.
- **События и атрибуция**: `tests/test_events_api.py` — CRUD типов событий, приём батчей событий, валидация типов, дедупликация, зависимости `requires_show_event_type_id`.
- **Отчёты**: `tests/test_reports_api.py` — валидация окна отчёта, базовая корректность ответа.

Негативные сценарии (400/401/403/404) покрыты в соответствующих тестах (например, `test_events_api.py::test_events_submit_invalid_body_*`, `test_users_api.py::test_auth_login_invalid_*`).

### Покрытие критериев и принцип набора тестов

Тесты выровнены по обязательным критериям (B1–B10): у каждого проверяемого критерия есть хотя бы один воспроизводимый сценарий (интеграционный или единичный). Количество тестов сознательно не раздувается: приоритет — **максимальное покрытие критериев при минимальном наборе**; явно дублирующие сценарии удалены. Юнит-тесты (`test_experiment_validation.py`) дополняют интеграционные там, где нужна быстрая проверка отдельных правил (например, валидация весов вариантов перед отправкой на ревью).

При запуске `pytest` вывод в консоли разбит по секциям (Health, Users, Flags, Experiments, Decide, Events, Reports), чтобы было видно, что именно тестируется.

### Команды запуска с покрытием

Все команды выполняются **из корня репозитория**.

1. Установка зависимостей для backend и тестов:

```bash
pip install -r backend/requirements.txt -r requirements-test.txt
```

2. Запуск инфраструктуры (PostgreSQL + backend) через Docker:

```bash
docker-compose up -d postgres backend
```

3. Сидинг тестовых данных (пользователи, метрики, типы событий и т.д.):

```bash
export API_BASE_URL=http://localhost:80
python tests/seed_test_data.py
```

4. Запуск тестов с измерением покрытия (через pytest-cov):

```bash
pip install pytest-cov 

pytest tests \
  --cov=backend \
  --cov-report=term-missing:skip-covered \
  --cov-report=xml:coverage.xml
```

- `--cov=backend` — измерение покрытия только по коду backend.
- `--cov-report=term-missing:skip-covered` — краткий отчёт в консоли (показывает непротестированные строки).
- `--cov-report=xml:coverage.xml` — XML-отчёт для CI/инструментов анализа.