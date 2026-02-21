# Autopilot Ramp-up — логика и интеграция

Доп. функция: умная раскатка по ступеням трафика с gates, safety actions и прозрачным логом решений.

---

## 1. Цель

- Ускорить получение данных за счёт автоматического повышения трафика при выполнении условий.
- Автоматически тормозить/останавливать при плохих метриках или срабатывании guardrails.
- Делать процесс прозрачным: текущая ступень, причина перехода или остановки, кто вмешался вручную.

---

## 2. Сущности (таблицы)

| Таблица | Назначение |
|--------|-------------|
| **ramp_plans** | План раскатки на эксперимент: окно наблюдения, gate_data_sufficiency, gate_safety, gate_data_health (JSONB). |
| **ramp_steps** | Ступени трафика (step_index, traffic_fraction), например 1% → 5% → 10% → 25% → 50% → 100%. |
| **ramp_safety_actions** | При каком триггере (guardrail_triggered, error_rate_high, latency_high, data_quality_critical) какое действие (pause, rollback_to_control, step_back) и уведомлять ли. |
| **experiment_ramp_state** | Текущее состояние: план, текущая ступень, режим (autopilot / manual / paused), время последней оценки, кто вручную переопределил. |
| **experiment_ramp_decision_log** | История решений: действие (step_up, step_back, pause, rollback, override, …), from/to step, reason (JSONB), triggered_by (autopilot/manual), user_id. |

---

## 3. Gates: когда можно увеличивать трафик

На каждом шаге (перед переходом на следующую ступень) автопилот проверяет три группы условий. Если все выполнены — переход на следующую ступень; иначе — остаёмся или выполняем safety action.

### 3.1 Достаточность данных (gate_data_sufficiency)

- **min_total_impressions** — за окно наблюдения (observation_window_seconds) общее число показов ≥ X.
- **min_impressions_per_variant** — по каждому варианту (A/B/n) показов ≥ Y.
- **min_minutes_on_step** — на текущей ступени прошло не менее T минут.

Источники данных: решения (decisions) и события (event_occurrences / exposure), агрегации по окну и по варианту — как в отчётах (reports).

### 3.2 Безопасность (gate_safety)

- **use_guardrails** — если true, проверять, что за окно не сработал ни один experiment guardrail (experiment_guardrail_history). Если сработал — gate не пройден, применяется safety action по trigger_type `guardrail_triggered`.
- **error_rate_threshold** — доля ошибок (например error_rate метрика) не выше порога.
- **latency_p95_ms** — p95 задержки не выше порога (могут быть отдельные «ramp-пороги», мягче или жёстче guardrails).

При нарушении — выбор действия из ramp_safety_actions по соответствующему trigger_type (error_rate_high, latency_high).

### 3.3 Здоровье данных (gate_data_health)

- **require_no_srm** — нет критического перекоса (SRM) по вариантам.
- **require_no_mass_rejected** — нет массовых rejected events (если в системе есть учёт отклонённых событий).

При нарушении — trigger_type `data_quality_critical`, действие из ramp_safety_actions.

---

## 4. Safety actions: что делать, если плохо

В ramp_safety_actions задаётся для каждого типа триггера:

- **pause** — поставить эксперимент на паузу (status → paused), записать в лог, при необходимости уведомить (notify).
- **rollback_to_control** — откатить эксперимент к контролю (если поддерживается: все пользователи получают контрольный вариант).
- **step_back** — откатить трафик на предыдущую ступень (current_step_index -= 1, audience_fraction и веса вариантов пересчитать по ramp_steps), обновить experiment и experiment_ramp_state, дать время стабилизироваться.

Выбор действия задаётся в плане и может отличаться по уровню критичности (например, при guardrail_triggered — pause, при data_quality_critical — step_back).

---

## 5. Прозрачность и управляемость

### 5.1 Лог решений (experiment_ramp_decision_log)

Система фиксирует:

- текущую ступень (через experiment_ramp_state.current_step_index);
- когда и почему перешли (action: step_up / step_back, from_step_index, to_step_index, reason);
- какие метрики/пороги проверяли (в reason: список проверок, значения, пороги);
- что именно нарушилось при остановке (в reason при action pause/step_back/rollback).

### 5.2 Режимы и ручное вмешательство

**Чем отличаются manual и paused:**

- **paused** — «автопилот на паузе»: автоматика выключена, раскатка заморожена на текущей ступени. Никто не меняет ступень; типично «подождать / разобраться», потом снова включить autopilot. Вызов **override_step в режиме paused запрещён** (ошибка `override_only_in_manual_mode`).
- **manual** — «ручное управление»: владелец сам ведёт раскатку. Ступени можно менять через **override_step**; автопилот не трогает трафик, пока режим не переключён обратно на autopilot.

В обоих режимах автопилот не выполняет автоматические safety actions и не делает step_up/step_back.

- **Остановить автопилот** — set_ramp_mode(experiment_id, "paused" | "manual", user_id).
- **Перезапустить автопилот** — set_ramp_mode(experiment_id, "autopilot", user_id).
- **Пропустить/выбрать ступень (override)** — только при mode=manual: override_step(experiment_id, to_step_index, user_id). Запись в лог с triggered_by=manual и user_id.

Все ручные действия пишутся в experiment_ramp_decision_log с triggered_by='manual' и user_id.

---

## 6. Порядок работы (интеграция)

1. **Создание плана** — до или после старта эксперимента: create_or_update_ramp_plan(experiment_id, observation_window_seconds, steps, gate_*, safety_actions). Ступени задают трафик на каждом шаге; при старте эксперимента можно выставить audience_fraction по первой ступени.
2. **Старт автопилота** — когда эксперимент уже running: start_autopilot(experiment_id). Создаётся experiment_ramp_state (current_step_index=0, mode=autopilot).
3. **Периодическая оценка (воркер/кроник)** — для экспериментов с experiment_ramp_state.mode='autopilot' и status='running':
   - загрузить ramp_plan, ramp_state, текущие метрики (показы по вариантам, error rate, latency p95, guardrail history, DQ флаги);
   - проверить safety: если сработал guardrail или нарушены ramp-пороги — применить соответствующее safety action (pause / rollback / step_back), обновить state и лог;
   - иначе проверить gates для текущей ступени; если все gates выполнены и есть следующая ступень — step_up: обновить audience_fraction и веса вариантов по ramp_steps[to_step_index], current_step_index, записать в лог;
   - иначе — записать no_change с reason (какие gate не прошли).
4. **Применение ступени к эксперименту** — при step_up/step_back нужно обновить experiments.audience_fraction и experiment_variants.weight так, чтобы сумма весов совпадала с трафиком выбранной ступени (и сохранялась доля между вариантами, если задана в плане).

---

## 7. Файлы модуля

- **types.py** — константы и ключи JSONB (gate_*, trigger_type, action, mode).
- **ramp_plan.py** — CRUD для ramp_plans, ramp_steps, ramp_safety_actions.
- **ramp_state.py** — experiment_ramp_state (get, start_autopilot, set_ramp_mode, override_step), experiment_ramp_decision_log (log_autopilot_decision, get_ramp_decision_log).
- **LOGIC.md** — этот документ.

Движок оценки (evaluator), который по расписанию проверяет gates и выполняет step_up/safety actions, целесообразно вынести в отдельный файл (например `ramp_evaluator.py`) и вызывать из воркера/кроника, чтобы не смешивать с основным API экспериментов.
