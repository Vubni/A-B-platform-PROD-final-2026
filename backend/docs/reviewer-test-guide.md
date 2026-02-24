# Руководство для тестирования: тестовые данные и сценарии

Документ содержит всё необходимое для проверки системы **только через Docker и curl** (без запуска Python): после `docker compose up -d` тестовые данные уже созданы, далее — получение токенов и сценарии через `curl`.

---

## 1. Предусловия и запуск

### 1.1 Запуск окружения

```bash
docker compose up -d
```

Дождаться готовности: `curl http://localhost:80/ready` должен вернуть **200** (до 180 секунд).

При старте backend автоматически создаются все тестовые данные (пользователи, флаг, типы событий, метрики, группа аппруверов) — **запускать Python или скрипт сида не нужно**.

### 1.2 Переменные для curl

Далее во всех примерах подставьте свой базовый URL и токены:

```bash
export BASE_URL="http://localhost:80"
```

---

## 2. Тестовые данные (создаются при старте backend)

| Сущность | Значение |
|----------|----------|
| **Пользователи** | По одному на роль (логин / пароль): |
| | `admin@test.com` / `admin123` — **admin** |
| | `experimenter@test.com` / `exp123` — **experimenter** |
| | `viewer@test.com` / `view123` — **viewer** |
| | `approver@test.com` / `app123` — **approver** |
| **Feature flag** | Ключ: `test_feature_flag`, тип: string, default: `control` |
| **Типы событий** | `demo_exposure`, `demo_click`, `demo_conversion` (conversion зависит от exposure) |
| **Метрики** | `demo_impressions`, `demo_conversions`, `demo_conversion_rate` (ratio) |
| **Группа аппруверов** | Для experimenter: min_approvals=1, в группе approver@test.com |

Для сценариев нужны: **ключ флага** (например, `test_feature_flag`) и при необходимости его **UUID** (из `GET /api/v1/flags`), а также **токены** (из `POST /api/v1/auth`).

---

## 3. Получение токенов и данных флага

Выполните по очереди и сохраните вывод в переменные.

**Токен admin:**
```bash
curl -s -X POST "$BASE_URL/api/v1/auth" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"admin123"}' | jq -r '.token'
```

**Токен experimenter:**
```bash
curl -s -X POST "$BASE_URL/api/v1/auth" \
  -H "Content-Type: application/json" \
  -d '{"email":"experimenter@test.com","password":"exp123"}' | jq -r '.token'
```

**Токен viewer** (нужен для decide):
```bash
curl -s -X POST "$BASE_URL/api/v1/auth" \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@test.com","password":"view123"}' | jq -r '.token'
```

**Токен approver:**
```bash
curl -s -X POST "$BASE_URL/api/v1/auth" \
  -H "Content-Type: application/json" \
  -d '{"email":"approver@test.com","password":"app123"}' | jq -r '.token'
```

**UUID флага** (ищем по ключу `test_feature_flag`, нужен для `flag_id` при создании эксперимента):
```bash
curl -s -X GET "$BASE_URL/api/v1/flags" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.flags[] | select(.key=="test_feature_flag") | .id' -r
```

Сохраните в переменные (пример для zsh/bash):
```bash
export ADMIN_TOKEN="<вставьте токен>"
export EXPERIMENTER_TOKEN="<вставьте токен>"
export VIEWER_TOKEN="<вставьте токен>"
export APPROVER_TOKEN="<вставьте токен>"
export FLAG_ID="<вставьте UUID флага>"        # используется как flag_id при создании эксперимента
export FLAG_KEY="test_feature_flag"           # ключ флага, используется в /decide
```

---

## 4. Сценарий 1.1 — Сквозной путь (happy-path)

Цель: флаг → эксперимент → ревью → запуск → decide → события → отчёт.

**Шаг 1 — Создать эксперимент (experimenter):**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/experiments" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"flag_id\": \"$FLAG_ID\",
    \"name\": \"Demo A/B\",
    \"audience_fraction\": 1.0,
    \"metrics\": [
      {\"metric_key\": \"demo_conversion_rate\", \"metric_type\": \"primary\"},
      {\"metric_key\": \"demo_impressions\", \"metric_type\": \"auxiliary\"}
    ]
  }"
```
Ожидаемо: **201**, в теле есть `id` эксперимента — сохраните как `EXP_ID`.

**Шаг 2 — Добавить варианты (experimenter):**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/experiments/$EXP_ID/variants" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant_name":"control","variant_value":"c","weight":0.5,"is_control":true}'

curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/experiments/$EXP_ID/variants" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"variant_name":"treatment","variant_value":"t","weight":0.5,"is_control":false}'
```
Ожидаемо: оба **201**.

**Шаг 3 — На ревью (experimenter):**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X PATCH "$BASE_URL/api/v1/experiments/$EXP_ID/status" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"on_review"}'
```
Ожидаемо: **200**.

**Шаг 4 — Одобрить (approver):**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X PATCH "$BASE_URL/api/v1/experiments/$EXP_ID/status" \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}'
```
Ожидаемо: **200**.

**Шаг 5 — Запустить (experimenter, владелец эксперимента):**
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X PATCH "$BASE_URL/api/v1/experiments/$EXP_ID/status" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}'
```
Ожидаемо: **200**.

**Шаг 6 — Выдать вариант (viewer, decide):**
```bash
curl -s -X POST "$BASE_URL/api/v1/decide" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"subject_id\":\"u42\",\"attributes\":{},\"flags\":[\"$FLAG_KEY\"]}"
```
Ожидаемо: **200**, в `flags[0]` есть `flag_value` ("c" или "t"), `decision_id`, `experiment`. Сохраните `decision_id` как `DECISION_ID`.

**Шаг 7 — Отправить экспозицию:**
```bash
curl -s -X POST "$BASE_URL/api/v1/events" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [{
      \"event_id\": \"ev-demo-1\",
      \"decision_id\": \"$DECISION_ID\",
      \"event_type_key\": \"demo_exposure\",
      \"subject_id\": \"u42\",
      \"timestamp\": \"2026-02-14T12:00:00Z\"
    }]
  }"
```
Ожидаемо: **200**, событие в `accepted`.

**Шаг 8 — Отправить конверсию:**
```bash
curl -s -X POST "$BASE_URL/api/v1/events" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"events\": [{
      \"event_id\": \"ev-demo-2\",
      \"decision_id\": \"$DECISION_ID\",
      \"event_type_key\": \"demo_conversion\",
      \"subject_id\": \"u42\",
      \"timestamp\": \"2026-02-14T12:00:00Z\"
    }]
  }"
```
Ожидаемо: **200**, событие в `accepted`.

**Шаг 9 — Отчёт по эксперименту:**
```bash
curl -s -X GET "$BASE_URL/api/v1/experiments/$EXP_ID/report?start=2026-02-01&end=2026-02-15" \
  -H "Authorization: Bearer $VIEWER_TOKEN"
```
Ожидаемо: **200**, в теле есть `variants` (разрез по вариантам), `metrics` с выбранными метриками.

---

## 5. Сценарий 1.2 — Детерминизм

При повторных вызовах decide для одного `subject_id` и того же флага **значение** `flag_value` и привязка к эксперименту/варианту должны совпадать (значение стабильно; `decision_id` в ответе может быть новым при каждом вызове).

```bash
curl -s -X POST "$BASE_URL/api/v1/decide" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"subject_id\":\"sub-fixed\",\"attributes\":{},\"flags\":[\"$FLAG_KEY\"]}"

curl -s -X POST "$BASE_URL/api/v1/decide" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"subject_id\":\"sub-fixed\",\"attributes\":{},\"flags\":[\"$FLAG_KEY\"]}"
```
Сравните в обоих ответах: `flags[0].flag_value` и наличие `experiment` — они должны совпадать.

---

## 6. Сценарий 3.1 — Default при отсутствии эксперимента (B2-1)

Используйте флаг, у которого нет активного эксперимента (например, создайте новый флаг через admin и возьмите его `key`, либо проверьте до шага 5 сценария 1.1).

```bash
curl -s -X POST "$BASE_URL/api/v1/decide" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"subject_id\":\"u99\",\"attributes\":{},\"flags\":[\"$FLAG_KEY\"]}"
```
Ожидаемо: **200**, в `flags[0]`: `flag_value` равен `default_value` флага, `experiment` отсутствует или null.

---

## 7. Негативные сценарии

### 7.1 Неверный логин
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/auth" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"wrong"}'
```
Ожидаемо: **401** (или **400**), токена нет.

### 7.2 Viewer не может создавать эксперименты
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/api/v1/experiments" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"flag_id\":\"$FLAG_ID\",\"name\":\"X\",\"audience_fraction\":1.0,\"metrics\":[]}"
```
Ожидаемо: **403**.

### 7.3 Событие без обязательных полей (B4-2)
```bash
curl -s -X POST "$BASE_URL/api/v1/events" \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"events":[{"event_id":"e1","subject_id":"u1","timestamp":"2026-02-14T12:00:00Z"}]}'
```
Ожидаемо: **200**, в теле событие в `rejected` или в `errors` (нет `decision_id`, `event_type_key`).

### 7.4 Дубликат события (B4-3)

Отправьте одно и то же событие (одинаковые `event_id`, `decision_id`, `event_type_key`, `subject_id`, `timestamp`) дважды. Второй раз дубликат не должен увеличивать счётчики в отчёте.

### 7.5 Недопустимый переход статуса (B3-4)

Для эксперимента в статусе `draft` (создайте новый эксперимент шагами 1–2 сценария 1.1 и не переводите его на ревью — сохраните его `id` как `EXP_DRAFT`):
```bash
curl -s -w "\nHTTP_CODE:%{http_code}" -X PATCH "$BASE_URL/api/v1/experiments/$EXP_DRAFT/status" \
  -H "Authorization: Bearer $EXPERIMENTER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"running"}'
```
Ожидаемо: **400** или **409**, статус остаётся `draft`.

---

## 8. Health, Ready, Метрики (B9)

```bash
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health"
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/ready"
curl -s "$BASE_URL/metrics"
```

---

## 9. Связь с критериями

| Сценарий | Критерий |
|----------|----------|
| 1.1 Сквозной путь | B1-5, B2-3, B4-4, B4-5, B6-1, B6-2, B6-3 |
| 1.2 Детерминизм | B2-4 |
| 3.1 Default без эксперимента | B2-1 |
| 7.1–7.5 Негативные | B3-3, B3-4, B4-2, B4-3 |
| Health/Ready/Metrics | B9-1, B9-2, B9-3 |

Полная матрица «задание → критерий → реализация → проверка»: `backend/docs/compliance-matrix.md`.  
Пакет сценариев с дополнительными граничными случаями и допфичами: `backend/docs/demo-scenarios.md`.
