# LOTTY A/B Platform GUI

React + Vite консоль для ручной проверки backend LOTTY A/B Platform.

## Запуск

```bash
npm install
npm run dev -- --host 127.0.0.1
```

GUI откроется на `http://127.0.0.1:5173`.

Backend ожидается на `http://localhost:18080`. В dev-режиме GUI использует `/__api`: это Vite proxy, который прокидывает запросы в Docker-backend и помогает избежать CORS-проблем.

## Production build

```bash
npm run build
```

После `npm run build` Vite proxy уже не работает. Если `VITE_API_BASE_URL` не задан, GUI автоматически обращается к backend на том же hostname, где открыт frontend, и порту `18080`: например `http://your-server-host:18080`.

Для явного адреса API создайте `.env.production` по примеру `.env.production.example`:

```bash
VITE_API_BASE_URL=http://your-server-host:18080
```

Также frontend можно поднять через Docker Compose из корня проекта: контейнер отдаёт статические файлы на `http://localhost:30080`.

## Быстрый вход и роли

В верхней панели есть выпадающий список аккаунтов. Он подставляет seed-логины из `backend/docs/reviewer-test-guide.md`:

- Администратор: `admin@test.com` / `admin123`
- Экспериментатор: `experimenter@test.com` / `exp123`
- Аппрувер: `approver@test.com` / `app123`
- Наблюдатель: `viewer@test.com` / `view123`
- Docker fallback admin: `admin@example.com` / `admin123`

После логина токен сохраняется в `localStorage`, а все последующие запросы идут с `Authorization: Bearer <token>`.

Кнопка `Быстрый сценарий по ролям` сама переключает роли:

1. admin создаёт или обновляет approver-группу для experimenter;
2. experimenter создаёт эксперимент, варианты и отправляет на ревью;
3. approver одобряет;
4. experimenter запускает;
5. viewer делает `decide`, отправляет события и открывает отчёт.

## Что можно проверить

- `/health`, `/ready`, `/metrics` через верхние индикаторы.
- Auth, users, approver groups в разделе `Доступ`.
- Event types и metric catalog в `Каталоги`.
- Feature flags CRUD в `Флаги`.
- Создание эксперимента, варианты, статусы, complete/archive в `Эксперименты`.
- Runtime flow `decide -> events` в `Decide & Events`.
- Reports по периоду в `Отчёты`.
- Guardrail upsert/list в `Guardrails`.
- Learning upsert/list в `Learnings`.
- Conflict domains/bindings в `Конфликты`.
- Autopilot ramp plan/state/log в `Ramp-up`.
- Любой endpoint swagger через `Raw API`.

Справа всегда виден API inspector: последний метод, путь, статус, request body и JSON response.
