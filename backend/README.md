# LOTTY A/B Platform — Backend

Бэкенд A/B-платформы Лотти: feature flags, эксперименты, выдача вариантов (decide), события, отчёты, guardrails.

## Описание системы

Платформа позволяет:
- хранить **feature flags** (ключ, тип, значение по умолчанию);
- запускать **эксперименты** на флагах и раздавать варианты по долям аудитории;
- отвечать продукту «что показать пользователю» через **Decision API**;
- принимать **события** (показы, конверсии, ошибки, латентность) и строить отчёты;
- реагировать на деградации через **guardrails**.

## API

| Группа | Эндпоинты |
|--------|-----------|
| **Health** | `GET /health`, `GET /ready`, `GET /metrics` |
| **Users** | `GET/POST /api/v1/users`, `GET/PATCH /api/v1/users/{id}`, `GET/PUT /api/v1/approver-groups` |
| **Feature Flags** | `POST /api/v1/flags`, `GET /api/v1/flags`, `GET/PATCH /api/v1/flags/{key}` |
| **Experiments** | `POST /api/v1/experiments`, `GET /api/v1/experiments`, `GET/PATCH /api/v1/experiments/{id}`, `POST .../submit-review`, `.../approve`, `.../request-changes`, `.../reject`, `.../start`, `.../pause`, `.../resume`, `.../complete`, `GET .../guardrail-history` |
| **Runtime Decide** | `POST /api/v1/decide` — получить значения флагов для субъекта |
| **Events** | `POST /api/v1/events`, `GET/POST /api/v1/event-types`, `GET/PATCH/DELETE /api/v1/event-types/{id}` |
| **Reports** | `GET /api/v1/experiments/{id}/report`, `GET/POST /api/v1/metrics` |

Swagger UI: `http://localhost/` (при запущенном приложении).

## Демо-сценарий happy-path

Путь **«выдача варианта → событие → результат»**:

1. **Создать флаг** (если ещё нет):
   ```bash
   curl -X POST http://localhost/api/v1/flags \
     -H "Content-Type: application/json" \
     -d '{"key": "button_color", "value_type": "string", "default_value": "green"}'
   ```

2. **Создать и запустить эксперимент** (через админский API): создать эксперимент с вариантами A/B, отправить на ревью, одобрить, запустить.

3. **Выдача варианта**:
   ```bash
   curl -X POST http://localhost/api/v1/decide \
     -H "Content-Type: application/json" \
     -d '{"subject_id": "u42", "attributes": {}, "flag_keys": ["button_color"]}'
   ```
   Ответ содержит `decisions` (значение для каждого флага) и `decision_id` для атрибуции событий.

4. **Событие**:
   ```bash
   curl -X POST http://localhost/api/v1/events \
     -H "Content-Type: application/json" \
     -d '{"events": [{"event_id": "ev-1", "decision_id": "<из шага 3>", "event_type": "exposure", "subject_id": "u42", "timestamp": "2026-02-14T12:00:00Z"}]}'
   ```

5. **Результат** — отчёт по эксперименту:
   ```bash
   curl "http://localhost/api/v1/experiments/{experiment_id}/report?start=2026-02-01&end=2026-02-15"
   ```

## Роли и аппрувер-группы

| Роль | Права |
|------|-------|
| **Admin** | Управление пользователями и ролями, настройка правил ревью |
| **Experimenter** | Создание экспериментов, отправка на ревью |
| **Approver** | Одобрение/отклонение экспериментов в рамках своей группы |
| **Viewer** | Только чтение |

### Fallback аппрувер-группы

Если для Experimenter не задана персональная аппрувер-группа, используется fallback:

1. **Персональная группа** — ищется `approver_groups` с `experimenter_id = <id>`. Если есть и в ней есть аппруверы — используется.
2. **Fallback-группа** — запись в `approver_groups` с `experimenter_id IS NULL` (одна на систему). Если есть и в ней есть аппруверы — используется.
3. **Иначе** — `min_approvals = 1`, `approver_ids = все пользователи с role = admin`.

Fallback настраивается через `PUT /api/v1/approver-groups` с `experimenter_id: null`.

## Структура бэкенда

```
backend/
├── api/           # Обработчики HTTP (flags, experiments, decide, events, reports, users, health)
├── functions/     # Логика и работа с БД (users, ...)
├── database/      # Подключение к PostgreSQL, миграции
├── docs/          # Схемы и документация
├── config.py      # Конфигурация БД, логирование
├── server.py      # Точка входа, маршруты, CORS
├── Dockerfile     # Сборка образа
└── requirements.txt
```

## Запуск без Docker (для разработки)

```bash
cd backend
pip install -r requirements.txt
# Переменные и т.д. (см. config.py)
python server.py
```

При локальном запуске PostgreSQL должен быть доступен (например, через порт 5433 из `docker/postgres`).
