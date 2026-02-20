# C4-диаграммы LOTTY A/B Platform (B7-5, B7-6, B7-7)

Три уровня C4: контекст системы, контейнеры, компоненты по критичному пути decide → event → report/guardrail.

---

## B7-5. C4 Context (уровень 1)

Внешние акторы и граница системы «LOTTY A/B Platform».

```mermaid
C4Context
    title System Context — LOTTY A/B Platform

    Person(analyst, "Аналитик / Experimenter", "Создаёт эксперименты, настраивает ревью, смотрит отчёты")
    Person(approver, "Approver", "Одобряет или отклоняет эксперименты перед запуском")
    Person(viewer, "Viewer / Продукт", "Читает значения флагов и отправляет события")

    System(lotty, "LOTTY A/B Platform", "Backend: флаги, эксперименты, выдача вариантов, приём событий, отчёты, guardrails")

    Rel(analyst, lotty, "Управляет экспериментами, смотрит отчёты")
    Rel(approver, lotty, "Ревьюит эксперименты")
    Rel(viewer, lotty, "POST /decide, POST /events, GET /report")
```

**Граница платформы:** один backend-сервис + БД; клиенты (продукт, аналитики, аппруверы) взаимодействуют через HTTP API.

---

## B7-6. C4 Container (уровень 2)

Основные контейнеры (сервисы/хранилища) и их ответственности.

```mermaid
C4Container
    title Container diagram — LOTTY A/B Platform

    Person(viewer, "Viewer / Продукт")
    Person(analyst, "Аналитик")

    System_Boundary(lotty, "LOTTY A/B Platform") {
        Container(backend, "Backend API", "Python, aiohttp", "HTTP API: флаги, эксперименты, decide, events, отчёты, guardrails, health/metrics")
        ContainerDb(db, "PostgreSQL", "PostgreSQL", "Флаги, эксперименты, решения, события, метрики, ревью, guardrail-история")
    }

    Rel(viewer, backend, "POST /decide, POST /events", "HTTPS")
    Rel(analyst, backend, "CRUD эксперименты, отчёты, ревью", "HTTPS")
    Rel(backend, db, "Чтение/запись", "TCP")
```

**Ключевые взаимодействия:** продукт → Backend (decide, events); аналитик → Backend (эксперименты, отчёты); Backend → БД (все данные).

---

## B7-7. C4 Component — критичный путь decide → event → report/guardrail

Детализация **одного** контейнера (Backend) по критичному потоку. Без детализации до классов.

```mermaid
C4Component
    title Component diagram — Backend, критичный путь decide → event → report/guardrail

    Container_Boundary(backend, "Backend API") {
        Component(decide_api, "Decide API", "aiohttp", "POST /decide: приём subject_id, attributes, flags; вызов decide-логики")
        Component(decide_logic, "Decide (логика)", "Python", "Выбор варианта по флагу/эксперименту, таргетинг, веса, лимиты участия; запись decisions")
        Component(events_api, "Events API", "aiohttp", "POST /events: приём батча событий; вызов обработки событий")
        Component(events_logic, "Events (логика)", "Python", "Валидация, дедупликация, атрибуция (decision_id, requires_show); запись event_occurrences; вызов проверки guardrails")
        Component(reports_logic, "Reports (логика)", "Python", "Расчёт метрик по окну и вариантам; формирование отчёта")
        Component(reports_api, "Reports API", "aiohttp", "GET .../report: параметры start/end; вызов reports-логики")
        Component(guardrails_logic, "Guardrails (логика)", "Python", "Проверка порогов guardrail-метрик по решениям; при превышении — pause/rollback и запись в experiment_guardrail_history")
        Component(db_access, "Database", "asyncpg", "Доступ к PostgreSQL: decisions, event_occurrences, experiments, experiment_guardrail_history и др.")
    }

    Rel(decide_api, decide_logic, "Вызов")
    Rel(decide_logic, db_access, "Чтение экспериментов/флагов; запись decisions")
    Rel(events_api, events_logic, "Вызов")
    Rel(events_logic, db_access, "Чтение/запись событий, типов, решений")
    Rel(events_logic, guardrails_logic, "Проверка после приёма событий")
    Rel(guardrails_logic, db_access, "Чтение метрик, запись истории guardrail; обновление статуса эксперимента")
    Rel(reports_api, reports_logic, "Вызов")
    Rel(reports_logic, db_access, "Чтение экспериментов, решений, событий, метрик")
```

**Поток:** Decide API → логика решений → БД; Events API → валидация/дедупликация/атрибуция → БД → (опционально) Guardrails → отчёт строится из тех же данных через Reports API → Reports logic → БД.

---

Матрица соответствия: `backend/docs/compliance-matrix.md`.  
Карта репозитория и ограничения: `backend/README.md`.
