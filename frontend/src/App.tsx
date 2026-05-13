import {
  Activity,
  BarChart3,
  BookOpen,
  Archive,
  ChevronDown,
  CheckCircle2,
  ClipboardCheck,
  Database,
  Edit3,
  Flag,
  FlaskConical,
  Gauge,
  GitBranch,
  History,
  KeyRound,
  Plus,
  Play,
  RefreshCw,
  Route,
  Send,
  ShieldAlert,
  SlidersHorizontal,
  TerminalSquare,
  UserPlus,
  Users,
  XCircle,
} from 'lucide-react'
import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }

type RequestLog = {
  id: string
  at: string
  method: HttpMethod
  path: string
  status: number | 'ERR'
  ok: boolean
  duration: number
  request?: unknown
  response: unknown
}

type ApiResult = { ok: boolean; status: number | 'ERR'; data: unknown }

type EndpointSpec = {
  method: HttpMethod
  path: string
  tag: string
  summary: string
  body?: string
}

type HealthState = {
  health?: 'ok' | 'fail'
  ready?: 'ok' | 'fail'
  metrics?: 'ok' | 'fail'
}

type FlagItem = {
  id?: string
  key: string
  value_type?: string
  default_value?: string
  owner?: string | null
  description?: string | null
}

type ExperimentItem = {
  id: string
  name?: string
  status?: string
  flag_id?: string
  flag_key?: string
  audience_fraction?: number
  variants?: VariantItem[]
  metrics?: unknown[]
}

type VariantItem = {
  id?: string
  variant_name?: string
  variant_value?: string
  weight?: number
  is_control?: boolean
}

type Catalogs = {
  flags: FlagItem[]
  experiments: ExperimentItem[]
  users: Array<Record<string, unknown>>
  approverGroups: Array<Record<string, unknown>>
  eventTypes: Array<Record<string, unknown>>
  metrics: Array<Record<string, unknown>>
  guardrails: Array<Record<string, unknown>>
  learnings: Array<Record<string, unknown>>
  conflictDomains: Array<Record<string, unknown>>
}

type Drafts = {
  register: { email: string; first_name: string; password: string }
  user: { id: string; email: string; first_name: string; password: string; role: string }
  approverGroup: { experimenter_id: string; approver_ids: string; min_approvals: number }
  flag: { key: string; value_type: string; default_value: string; owner: string; description: string; metadata: string }
  metric: { key: string; name: string; unit: string; description: string; aggregation_rule: string; event_expectations: string; attribution_rule: string }
  eventType: { key: string; display_name: string; description: string; is_critical: boolean; required_params: string; requires_show_event_type_id: string }
  experiment: { name: string; flag_id: string; audience_fraction: number; targeting_rule: string; metrics: string }
  variant: { experiment_id: string; variant_name: string; variant_value: string; weight: number; is_control: boolean }
  status: { experiment_id: string; status: string; comment: string }
  decide: { subject_id: string; flags: string; attributes: string }
  event: { decision_id: string; subject_id: string; event_type_key: string; payload: string }
  report: { experiment_id: string; start: string; end: string; include_dynamics: boolean }
  complete: { experiment_id: string; completion_outcome: string; completion_winner_variant_id: string; comment: string }
  learning: { experiment_id: string; hypothesis: string; notes: string; primary_metric_key: string; result_action: string; result_outcome: string; effect_summary: string; product_tags: string }
  guardrail: { metric_key: string; threshold: number; action: string; window_seconds: number }
  conflictDomain: { key: string; name: string; default_policy: string; description: string }
  conflictBinding: { experiment_id: string; domain_id: string; policy: string; priority_tier: number; bid_value: number; is_enabled: boolean }
  rampPlan: {
    experiment_id: string
    step1: number
    step2: number
    step3: number
    observation_window_seconds: number
    min_total_impressions: number
    min_impressions_per_variant: number
    min_minutes_on_step: number
    use_guardrails: boolean
    error_rate_threshold: number
    latency_p95_ms: number
    safety_action: string
  }
  raw: { method: HttpMethod; path: string; body: string }
}

const nav = [
  { id: 'overview', label: 'Обзор', icon: Gauge },
  { id: 'demo', label: 'Демо A/B', icon: Play },
  { id: 'access', label: 'Доступ', icon: Users },
  { id: 'catalog', label: 'Каталоги', icon: Database },
  { id: 'flags', label: 'Флаги', icon: Flag },
  { id: 'experiments', label: 'Эксперименты', icon: FlaskConical },
  { id: 'runtime', label: 'Решения и события', icon: Route },
  { id: 'reports', label: 'Отчёты', icon: BarChart3 },
  { id: 'safety', label: 'Ограничители', icon: ShieldAlert },
  { id: 'learnings', label: 'Выводы', icon: BookOpen },
  { id: 'conflicts', label: 'Конфликты', icon: GitBranch },
  { id: 'ramp', label: 'Раскатка', icon: SlidersHorizontal },
  { id: 'raw', label: 'Произвольный API', icon: TerminalSquare },
] as const

const statuses = ['draft', 'on_review', 'approved', 'running', 'paused', 'rejected', 'completed', 'archived']
const demoStamp = () => new Date().toISOString().replace(/[-:.TZ]/g, '').slice(0, 14)

const swaggerEndpoints: EndpointSpec[] = [
  { method: 'GET', path: '/health', tag: 'Health', summary: 'Проба живости' },
  { method: 'GET', path: '/ready', tag: 'Health', summary: 'Проба готовности' },
  { method: 'GET', path: '/metrics', tag: 'Metrics', summary: 'Экспорт метрик Prometheus' },
  { method: 'POST', path: '/api/v1/register', tag: 'Auth', summary: 'Регистрация', body: '{"email":"new_user@example.com","first_name":"New User","password":"demo12345"}' },
  { method: 'POST', path: '/api/v1/auth', tag: 'Auth', summary: 'Авторизация', body: '{"email":"experimenter@test.com","password":"exp123"}' },
  { method: 'GET', path: '/api/v1/users?role=viewer', tag: 'Users', summary: 'Список пользователей с фильтром по роли' },
  { method: 'POST', path: '/api/v1/users', tag: 'Users', summary: 'Создать пользователя', body: '{"email":"tester@example.com","first_name":"Tester","password":"demo12345","role":"viewer"}' },
  { method: 'GET', path: '/api/v1/users/{id}', tag: 'Users', summary: 'Получить пользователя по ID' },
  { method: 'PATCH', path: '/api/v1/users/{id}', tag: 'Users', summary: 'Обновить пользователя', body: '{"first_name":"Updated","role":"viewer"}' },
  { method: 'GET', path: '/api/v1/approver-groups', tag: 'Users', summary: 'Список групп аппруверов' },
  { method: 'POST', path: '/api/v1/approver-groups', tag: 'Users', summary: 'Создать группу аппруверов', body: '{"experimenter_id":null,"approver_ids":[],"min_approvals":1}' },
  { method: 'PATCH', path: '/api/v1/approver-groups/{id}', tag: 'Users', summary: 'Обновить группу аппруверов', body: '{"approver_ids":[],"min_approvals":1}' },
  { method: 'GET', path: '/api/v1/flags', tag: 'Feature Flags', summary: 'Список feature flags' },
  { method: 'POST', path: '/api/v1/flags', tag: 'Feature Flags', summary: 'Создать feature flag', body: '{"key":"new_flag","value_type":"string","default_value":"control","owner":"growth","description":"Demo flag","metadata":{}}' },
  { method: 'GET', path: '/api/v1/flags/{key}', tag: 'Feature Flags', summary: 'Получить feature flag' },
  { method: 'PATCH', path: '/api/v1/flags/{key}', tag: 'Feature Flags', summary: 'Обновить значение по умолчанию feature flag', body: '{"default_value":"treatment"}' },
  { method: 'GET', path: '/api/v1/experiments', tag: 'Experiments', summary: 'Список экспериментов' },
  { method: 'POST', path: '/api/v1/experiments', tag: 'Experiments', summary: 'Создать эксперимент', body: '{"name":"Button color A/B","flag_id":"{flag_id}","audience_fraction":0.5,"targeting_rule":null,"metrics":[{"metric_key":"demo_click_rate","metric_type":"primary"}]}' },
  { method: 'GET', path: '/api/v1/experiments/{id}', tag: 'Experiments', summary: 'Получить эксперимент' },
  { method: 'PATCH', path: '/api/v1/experiments/{id}', tag: 'Experiments', summary: 'Обновить эксперимент', body: '{"name":"Updated experiment","audience_fraction":0.5,"targeting_rule":null}' },
  { method: 'PATCH', path: '/api/v1/experiments/{id}/status', tag: 'Experiments', summary: 'Обновить статус эксперимента', body: '{"status":"on_review","comment":"Комментарий"}' },
  { method: 'POST', path: '/api/v1/experiments/{id}/complete', tag: 'Experiments', summary: 'Завершить эксперимент', body: '{"completion_outcome":"no_effect","comment":"Решение зафиксировано","completion_winner_variant_id":null}' },
  { method: 'POST', path: '/api/v1/experiments/{id}/archive', tag: 'Experiments', summary: 'Архивировать эксперимент' },
  { method: 'POST', path: '/api/v1/experiments/{id}/variants', tag: 'Experiments', summary: 'Добавить вариант к эксперименту', body: '{"variant_name":"treatment","variant_value":"treatment","weight":0.5,"is_control":false}' },
  { method: 'PATCH', path: '/api/v1/experiments/{id}/variants/{variant_id}', tag: 'Experiments', summary: 'Обновить вариант эксперимента', body: '{"variant_value":"updated","weight":0.5,"is_control":false}' },
  { method: 'DELETE', path: '/api/v1/experiments/{id}/variants/{variant_id}', tag: 'Experiments', summary: 'Удалить вариант эксперимента' },
  { method: 'GET', path: '/api/v1/experiments/{id}/guardrail-history', tag: 'Experiments', summary: 'История срабатываний guardrail' },
  { method: 'GET', path: '/api/v1/experiments/{id}/ramp-plan', tag: 'Autopilot Ramp-up', summary: 'Получить план раскатки' },
  { method: 'PUT', path: '/api/v1/experiments/{id}/ramp-plan', tag: 'Autopilot Ramp-up', summary: 'Создать или обновить план раскатки', body: '{"observation_window_seconds":3600,"steps":[{"traffic_fraction":0.1},{"traffic_fraction":0.25}],"gate_data_sufficiency":{"min_total_impressions":1000,"min_impressions_per_variant":200,"min_minutes_on_step":60}}' },
  { method: 'DELETE', path: '/api/v1/experiments/{id}/ramp-plan', tag: 'Autopilot Ramp-up', summary: 'Удалить план раскатки' },
  { method: 'GET', path: '/api/v1/experiments/{id}/ramp-state', tag: 'Autopilot Ramp-up', summary: 'Получить состояние автопилота' },
  { method: 'POST', path: '/api/v1/experiments/{id}/ramp-start', tag: 'Autopilot Ramp-up', summary: 'Запустить автопилот' },
  { method: 'PATCH', path: '/api/v1/experiments/{id}/ramp-mode', tag: 'Autopilot Ramp-up', summary: 'Установить режим автопилота', body: '{"mode":"autopilot"}' },
  { method: 'POST', path: '/api/v1/experiments/{id}/ramp-override', tag: 'Autopilot Ramp-up', summary: 'Ручной переход на ступень', body: '{"to_step_index":1}' },
  { method: 'GET', path: '/api/v1/experiments/{id}/ramp-decision-log?limit=100', tag: 'Autopilot Ramp-up', summary: 'История решений автопилота' },
  { method: 'GET', path: '/api/v1/guardrails', tag: 'Guardrails', summary: 'Список guardrail-правил по метрикам' },
  { method: 'POST', path: '/api/v1/guardrails', tag: 'Guardrails', summary: 'Создать или обновить guardrail по метрике', body: '{"metric_key":"demo_click_rate","threshold":0.1,"action":"pause","window_seconds":3600}' },
  { method: 'GET', path: '/api/v1/guardrails/{metric_key}', tag: 'Guardrails', summary: 'Получить guardrail по метрике' },
  { method: 'DELETE', path: '/api/v1/guardrails/{metric_key}', tag: 'Guardrails', summary: 'Удалить guardrail по метрике' },
  { method: 'GET', path: '/api/v1/conflict-domains', tag: 'Conflict domains', summary: 'Список конфликтных доменов' },
  { method: 'POST', path: '/api/v1/conflict-domains', tag: 'Conflict domains', summary: 'Создать конфликтный домен', body: '{"key":"checkout","name":"Checkout","default_policy":"mutual_exclusion","description":"Зона оформления"}' },
  { method: 'GET', path: '/api/v1/conflict-domains/{id}', tag: 'Conflict domains', summary: 'Получить конфликтный домен по ID' },
  { method: 'PATCH', path: '/api/v1/conflict-domains/{id}', tag: 'Conflict domains', summary: 'Обновить конфликтный домен', body: '{"name":"Checkout updated","default_policy":"priority","description":"Описание"}' },
  { method: 'DELETE', path: '/api/v1/conflict-domains/{id}', tag: 'Conflict domains', summary: 'Удалить конфликтный домен' },
  { method: 'GET', path: '/api/v1/experiments/{id}/conflict-bindings', tag: 'Conflict domains', summary: 'Список привязок эксперимента к доменам' },
  { method: 'POST', path: '/api/v1/experiments/{id}/conflict-bindings', tag: 'Conflict domains', summary: 'Добавить или обновить привязку к домену', body: '{"domain_id":"{domain_id}","policy":"mutual_exclusion","priority_tier":1,"bid_value":1,"is_enabled":true}' },
  { method: 'DELETE', path: '/api/v1/experiments/{id}/conflict-bindings/{domain_id}', tag: 'Conflict domains', summary: 'Удалить привязку к домену' },
  { method: 'GET', path: '/api/v1/experiments/{id}/conflict-preflight', tag: 'Conflict domains', summary: 'Preflight конфликтов при запуске' },
  { method: 'GET', path: '/api/v1/experiments/{id}/conflict-log', tag: 'Conflict domains', summary: 'Аудит конфликтов по эксперименту' },
  { method: 'POST', path: '/api/v1/decide', tag: 'Runtime Decide', summary: 'Получить значения флагов для субъекта', body: '{"subject_id":"u42","flags":["test_feature_flag"],"attributes":{"country":"RU","platform":"web"}}' },
  { method: 'POST', path: '/api/v1/events', tag: 'Events', summary: 'Отправить пакет событий', body: '{"events":[{"event_id":"evt-1","decision_id":"{decision_id}","event_type_key":"demo_click","subject_id":"u42","timestamp":"2026-02-20T11:10:00Z","payload":{}}]}' },
  { method: 'GET', path: '/api/v1/event-types?status=active', tag: 'Events', summary: 'Список типов событий' },
  { method: 'POST', path: '/api/v1/event-types', tag: 'Events', summary: 'Создать тип события', body: '{"key":"demo_click","display_name":"Demo click","description":"Клик","is_critical":false,"required_params":{}}' },
  { method: 'GET', path: '/api/v1/event-types/{id}', tag: 'Events', summary: 'Получить тип события' },
  { method: 'PATCH', path: '/api/v1/event-types/{id}', tag: 'Events', summary: 'Обновить тип события', body: '{"display_name":"Updated event","description":"Описание","is_critical":false}' },
  { method: 'DELETE', path: '/api/v1/event-types/{id}', tag: 'Events', summary: 'Архивировать тип события' },
  { method: 'GET', path: '/api/v1/experiments/{id}/report?start=2026-02-01&end=2026-12-31', tag: 'Reports', summary: 'Отчёт по эксперименту' },
  { method: 'GET', path: '/api/v1/learnings?q=demo&limit=20', tag: 'Learnings', summary: 'Поиск learnings' },
  { method: 'GET', path: '/api/v1/learnings/{id}', tag: 'Learnings', summary: 'Получить learning по ID' },
  { method: 'GET', path: '/api/v1/learnings/{id}/audit', tag: 'Learnings', summary: 'История изменений learning' },
  { method: 'GET', path: '/api/v1/learnings/{id}/similar', tag: 'Learnings', summary: 'Похожие эксперименты для learning' },
  { method: 'GET', path: '/api/v1/experiments/{id}/learning', tag: 'Learnings', summary: 'Получить learning по эксперименту' },
  { method: 'PUT', path: '/api/v1/experiments/{id}/learning', tag: 'Learnings', summary: 'Создать или обновить learning для эксперимента', body: '{"hypothesis":"Гипотеза","notes":"Вывод","primary_metric_key":"demo_click_rate","result_action":"continue","result_outcome":"no_effect","product_tags":[],"platforms":["web"],"countries":[],"app_versions":[],"variant_structure":{},"is_completed":true}' },
  { method: 'GET', path: '/api/v1/metrics', tag: 'Reports', summary: 'Каталог метрик' },
  { method: 'POST', path: '/api/v1/metrics', tag: 'Reports', summary: 'Создать метрику в каталоге', body: '{"key":"demo_clicks","name":"Demo clicks","aggregation_rule":{"kind":"count_events","event_type_key":"demo_click"},"event_expectations":{"demo_click":"higher"}}' },
  { method: 'GET', path: '/api/v1/metrics/{key}', tag: 'Reports', summary: 'Получить метрику по ключу' },
  { method: 'PATCH', path: '/api/v1/metrics/{key}', tag: 'Reports', summary: 'Обновить метрику в каталоге', body: '{"name":"Updated metric","aggregation_rule":{"kind":"count_events","event_type_key":"demo_click"},"event_expectations":{"demo_click":"higher"}}' },
]

const accountPresets = [
  { id: 'admin-seed', label: 'Администратор', role: 'admin', email: 'admin@test.com', password: 'admin123', note: 'Пользователи и approver-группы' },
  { id: 'experimenter-seed', label: 'Экспериментатор', role: 'experimenter', email: 'experimenter@test.com', password: 'exp123', note: 'Флаги, эксперименты, варианты, запуск' },
  { id: 'approver-seed', label: 'Аппрувер', role: 'approver', email: 'approver@test.com', password: 'app123', note: 'Одобрение и отклонение экспериментов' },
  { id: 'viewer-seed', label: 'Наблюдатель', role: 'viewer', email: 'viewer@test.com', password: 'view123', note: 'Runtime decide, события, отчёты' },
  { id: 'docker-admin', label: 'Docker admin', role: 'admin', email: 'admin@example.com', password: 'admin123', note: 'Fallback из docker-compose' },
] as const

const initialDrafts: Drafts = {
  register: { email: `new_user_${demoStamp()}@example.com`, first_name: 'New User', password: 'demo12345' },
  user: { id: '', email: `tester_${demoStamp()}@example.com`, first_name: 'Demo Tester', password: 'demo12345', role: 'viewer' },
  approverGroup: { experimenter_id: '', approver_ids: '', min_approvals: 1 },
  flag: { key: `button_color_${demoStamp()}`, value_type: 'string', default_value: 'green', owner: 'growth', description: 'Цвет кнопки покупки', metadata: '{"surface":"checkout"}' },
  metric: {
    key: `demo_clicks_${demoStamp()}`,
    name: 'Demo clicks',
    unit: 'events',
    description: 'Количество кликов',
    aggregation_rule: '{"kind":"count_events","event_type_key":"demo_click"}',
    event_expectations: '{"demo_click":"higher"}',
    attribution_rule: '{"requires_decision":true}',
  },
  eventType: { key: `demo_click_${demoStamp()}`, display_name: 'Demo click', description: 'Клик по тестовой кнопке', is_critical: false, required_params: '{}', requires_show_event_type_id: '' },
  experiment: { name: `Button color A/B ${demoStamp()}`, flag_id: '', audience_fraction: 0.5, targeting_rule: '', metrics: '[{"metric_key":"demo_click_rate","metric_type":"primary"}]' },
  variant: { experiment_id: '', variant_name: 'A control', variant_value: 'green', weight: 0.25, is_control: true },
  status: { experiment_id: '', status: 'on_review', comment: 'Проверка GUI lifecycle' },
  decide: { subject_id: 'u42', flags: 'test_feature_flag', attributes: '{"country":"RU","platform":"web"}' },
  event: { decision_id: '', subject_id: 'u42', event_type_key: 'demo_click', payload: '{"source":"gui"}' },
  report: { experiment_id: '', start: '2026-02-01', end: '2026-02-15', include_dynamics: true },
  complete: { experiment_id: '', completion_outcome: 'no_effect', completion_winner_variant_id: '', comment: 'Решение зафиксировано из GUI' },
  learning: {
    experiment_id: '',
    hypothesis: 'Изменение варианта улучшит целевую метрику без деградации guardrails',
    notes: 'Заполнено через GUI для проверки требования learnings before complete',
    primary_metric_key: 'demo_click_rate',
    result_action: 'continue',
    result_outcome: 'no_effect',
    effect_summary: 'Эффект не подтверждён на демо-данных',
    product_tags: 'checkout,button',
  },
  guardrail: { metric_key: 'demo_conversions', threshold: 10, action: 'pause', window_seconds: 3600 },
  conflictDomain: { key: `checkout_${demoStamp()}`, name: 'Checkout', default_policy: 'mutual_exclusion', description: 'Зона оформления заказа' },
  conflictBinding: { experiment_id: '', domain_id: '', policy: 'mutual_exclusion', priority_tier: 1, bid_value: 1, is_enabled: true },
  rampPlan: {
    experiment_id: '',
    step1: 0.1,
    step2: 0.25,
    step3: 0.5,
    observation_window_seconds: 3600,
    min_total_impressions: 10,
    min_impressions_per_variant: 5,
    min_minutes_on_step: 1,
    use_guardrails: true,
    error_rate_threshold: 0.2,
    latency_p95_ms: 1000,
    safety_action: 'pause',
  },
  raw: { method: 'GET', path: '/health', body: '{}' },
}

function App() {
  const [active, setActive] = useState<(typeof nav)[number]['id']>('overview')
  const [apiBase, setApiBase] = useStickyState('lotty_api_base', '/__api')
  const [selectedAccount, setSelectedAccount] = useStickyState('lotty_account', 'experimenter-seed')
  const [email, setEmail] = useStickyState('lotty_email', 'experimenter@test.com')
  const [password, setPassword] = useStickyState('lotty_password', 'exp123')
  const [token, setToken] = useStickyState('lotty_token', '')
  const [currentUser, setCurrentUser] = useState<unknown>(null)
  const [health, setHealth] = useState<HealthState>({})
  const [catalogs, setCatalogs] = useState<Catalogs>({ flags: [], experiments: [], users: [], approverGroups: [], eventTypes: [], metrics: [], guardrails: [], learnings: [], conflictDomains: [] })
  const [drafts, setDrafts] = useState<Drafts>(initialDrafts)
  const [logs, setLogs] = useState<RequestLog[]>([])
  const [busy, setBusy] = useState(false)
  const [scenarioRunning, setScenarioRunning] = useState(false)

  const lastLog = logs[0]
  const activeExperiment = catalogs.experiments.find((item) => item.id === drafts.report.experiment_id || item.id === drafts.status.experiment_id || item.id === drafts.variant.experiment_id)
  const runningCount = catalogs.experiments.filter((item) => item.status === 'running').length
  const draftCount = catalogs.experiments.filter((item) => item.status === 'draft').length
  const selectedPreset = accountPresets.find((account) => account.id === selectedAccount) || accountPresets[1]

  const api = async (method: HttpMethod, path: string, body?: unknown, options?: { silent?: boolean; authToken?: string }) => {
    const started = performance.now()
    const normalizedBase = apiBase.replace(/\/$/, '')
    const normalizedPath = path.startsWith('/') ? path : `/${path}`
    try {
      const response = await fetch(`${normalizedBase}${normalizedPath}`, {
        method,
        headers: {
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(options?.authToken || token ? { Authorization: `Bearer ${options?.authToken || token}` } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      const text = await response.text()
      const data = parseMaybeJson(text)
      if (!options?.silent) {
        pushLog({ method, path: normalizedPath, status: response.status, ok: response.ok, duration: performance.now() - started, request: body, response: data })
      }
      return { ok: response.ok, status: response.status, data }
    } catch (error) {
      const data = error instanceof Error ? { error: error.message } : { error: String(error) }
      if (!options?.silent) {
        pushLog({ method, path: normalizedPath, status: 'ERR', ok: false, duration: performance.now() - started, request: body, response: data })
      }
      return { ok: false, status: 'ERR' as const, data }
    }
  }

  const pushLog = (entry: Omit<RequestLog, 'id' | 'at'>) => {
    setLogs((prev) => [{ ...entry, id: crypto.randomUUID(), at: new Date().toLocaleTimeString('ru-RU') }, ...prev].slice(0, 30))
  }

  const applyAccountPreset = (presetId: string) => {
    const preset = accountPresets.find((account) => account.id === presetId)
    setSelectedAccount(presetId)
    if (!preset) return
    setEmail(preset.email)
    setPassword(preset.password)
  }

  const refreshAll = async (authToken = token, includeUsers = isRecord(currentUser) && currentUser.role === 'admin', includeMetrics = isRecord(currentUser) && currentUser.role === 'experimenter') => {
    setBusy(true)
    const [healthRes, readyRes, metricsRes] = await Promise.all([
      api('GET', '/health', undefined, { silent: true }),
      api('GET', '/ready', undefined, { silent: true }),
      api('GET', '/metrics', undefined, { silent: true }),
    ])
    setHealth({ health: healthRes.ok ? 'ok' : 'fail', ready: readyRes.ok ? 'ok' : 'fail', metrics: metricsRes.ok ? 'ok' : 'fail' })

    if (!authToken) {
      setBusy(false)
      return
    }

    const keepIfFailed = <T,>(res: ApiResult, key: string, previous: T[]) => (res.ok ? arrayFrom(res.data, key) as T[] : previous)
    const includeAdminCatalogs = includeUsers
    const requests = await Promise.all([
      api('GET', '/api/v1/flags', undefined, { silent: true, authToken }),
      api('GET', '/api/v1/experiments', undefined, { silent: true, authToken }),
      includeAdminCatalogs ? api('GET', '/api/v1/users', undefined, { silent: true, authToken }) : Promise.resolve({ ok: true, status: 200, data: { users: catalogs.users } }),
      includeAdminCatalogs ? api('GET', '/api/v1/approver-groups', undefined, { silent: true, authToken }) : Promise.resolve({ ok: true, status: 200, data: { approver_groups: catalogs.approverGroups } }),
      api('GET', '/api/v1/event-types', undefined, { silent: true, authToken }),
      includeMetrics ? api('GET', '/api/v1/metrics', undefined, { silent: true, authToken }) : Promise.resolve({ ok: true, status: 200, data: { metrics: catalogs.metrics } }),
      api('GET', '/api/v1/guardrails', undefined, { silent: true, authToken }),
      api('GET', '/api/v1/learnings', undefined, { silent: true, authToken }),
      api('GET', '/api/v1/conflict-domains', undefined, { silent: true, authToken }),
    ])

    const next = {
      flags: keepIfFailed<FlagItem>(requests[0], 'flags', catalogs.flags),
      experiments: keepIfFailed<ExperimentItem>(requests[1], 'experiments', catalogs.experiments),
      users: keepIfFailed<Record<string, unknown>>(requests[2], 'users', catalogs.users),
      approverGroups: keepIfFailed<Record<string, unknown>>(requests[3], 'approver_groups', catalogs.approverGroups),
      eventTypes: keepIfFailed<Record<string, unknown>>(requests[4], 'event_types', catalogs.eventTypes),
      metrics: keepIfFailed<Record<string, unknown>>(requests[5], 'metrics', catalogs.metrics),
      guardrails: keepIfFailed<Record<string, unknown>>(requests[6], 'guardrails', catalogs.guardrails),
      learnings: keepIfFailed<Record<string, unknown>>(requests[7], 'learnings', catalogs.learnings),
      conflictDomains: keepIfFailed<Record<string, unknown>>(requests[8], 'conflict_domains', catalogs.conflictDomains),
    }
    setCatalogs(next)
    setDrafts((prev) => hydrateDraftIds(prev, next))
    setBusy(false)
  }

  const loginWithCredentials = async (credentials: { email: string; password: string }) => {
    const res = await api('POST', '/api/v1/auth', credentials)
    if (res.ok && isRecord(res.data)) {
      const nextToken = typeof res.data.token === 'string' ? res.data.token : ''
      setToken(nextToken)
      setCurrentUser(res.data.user)
      const userRole = isRecord(res.data.user) && typeof res.data.user.role === 'string' ? res.data.user.role : ''
      await refreshAll(nextToken, userRole === 'admin', userRole === 'experimenter')
      return { token: nextToken, user: res.data.user }
    }
    return { token: '', user: null }
  }

  const login = async (event?: FormEvent) => {
    event?.preventDefault()
    setBusy(true)
    await loginWithCredentials({ email, password })
    setBusy(false)
  }

  const register = async (payload: { email: string; first_name: string; password: string }) => {
    setBusy(true)
    const res = await api('POST', '/api/v1/register', payload)
    if (res.ok && isRecord(res.data)) {
      const nextToken = typeof res.data.token === 'string' ? res.data.token : ''
      setEmail(payload.email)
      setPassword(payload.password)
      setToken(nextToken)
      setCurrentUser(res.data.user)
      const userRole = isRecord(res.data.user) && typeof res.data.user.role === 'string' ? res.data.user.role : ''
      await refreshAll(nextToken, userRole === 'admin', userRole === 'experimenter')
    }
    setBusy(false)
  }

  useEffect(() => {
    refreshAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const updateDraft = <K extends keyof Drafts>(section: K, patch: Partial<Drafts[K]>) => {
    setDrafts((prev) => ({ ...prev, [section]: { ...prev[section], ...patch } }))
  }

  const ensureDemoRuntimeCatalog = async (authToken: string, updateAuthToken = authToken) => {
    const [eventTypesRes, metricsRes] = await Promise.all([
      api('GET', '/api/v1/event-types', undefined, { authToken }),
      api('GET', '/api/v1/metrics', undefined, { authToken }),
    ])
    const existingEventTypes = arrayFrom(eventTypesRes.data, 'event_types') as Array<Record<string, unknown>>
    const existingMetrics = arrayFrom(metricsRes.data, 'metrics') as Array<Record<string, unknown>>
    const metricByKey = (key: string) => existingMetrics.find((item) => item.key === key)
    if (!existingEventTypes.some((item) => item.key === 'demo_exposure')) {
      await api('POST', '/api/v1/event-types', { key: 'demo_exposure', display_name: 'Demo exposure', description: 'Показ демо-варианта', is_critical: false, required_params: {} }, { authToken })
    }
    if (!existingEventTypes.some((item) => item.key === 'demo_click')) {
      await api('POST', '/api/v1/event-types', { key: 'demo_click', display_name: 'Demo click', description: 'Клик по CTA в демо', is_critical: false, required_params: {} }, { authToken })
    }
    const exposureMetric = {
      name: 'Demo impressions',
      unit: 'events',
      description: 'Demo exposures counted by subject',
      aggregation_rule: { kind: 'count_events', event_type_key: 'demo_exposure', aggregation_unit: 'subject' },
      event_expectations: { demo_exposure: 'higher' },
      attribution_rule: { requires_decision: true },
    }
    const clickMetric = {
      name: 'Demo clicks',
      unit: 'events',
      description: 'Demo CTA clicks counted by subject',
      aggregation_rule: { kind: 'count_events', event_type_key: 'demo_click', aggregation_unit: 'subject' },
      event_expectations: { demo_click: 'higher' },
      attribution_rule: { requires_decision: true },
    }
    const rateMetric = {
      name: 'Demo click rate',
      unit: 'ratio',
      description: 'Demo clicks / demo impressions',
      aggregation_rule: { kind: 'ratio', numerator_metric_key: 'demo_clicks', denominator_metric_key: 'demo_impressions', aggregation_unit: 'subject' },
      event_expectations: { demo_click: 'higher' },
      attribution_rule: { requires_decision: true },
    }
    if (!metricByKey('demo_impressions')) {
      await api('POST', '/api/v1/metrics', { key: 'demo_impressions', ...exposureMetric }, { authToken })
    }
    if (!metricByKey('demo_clicks')) {
      await api('POST', '/api/v1/metrics', { key: 'demo_clicks', ...clickMetric }, { authToken })
    }
    const existingRate = metricByKey('demo_click_rate')
    const existingRateRule = isRecord(existingRate?.aggregation_rule) ? existingRate.aggregation_rule : {}
    const rateIsCurrent = existingRateRule.numerator_metric_key === 'demo_clicks' && existingRateRule.denominator_metric_key === 'demo_impressions'
    if (!existingRate) {
      await api('POST', '/api/v1/metrics', { key: 'demo_click_rate', ...rateMetric }, { authToken })
    } else if (!rateIsCurrent) {
      await api('PATCH', '/api/v1/metrics/demo_click_rate', rateMetric, { authToken: updateAuthToken })
    }
  }

  const runScenario = async () => {
    setScenarioRunning(true)
    const stamp = demoStamp()
    const admin = accountPresets.find((account) => account.role === 'admin')!
    const experimenter = accountPresets.find((account) => account.role === 'experimenter')!
    const approver = accountPresets.find((account) => account.role === 'approver')!
    const viewer = accountPresets.find((account) => account.role === 'viewer')!

    const adminAuth = await loginWithCredentials(admin)
    if (adminAuth.token) {
      const usersRes = await api('GET', '/api/v1/users', undefined, { authToken: adminAuth.token })
      const users = arrayFrom(usersRes.data, 'users') as Array<Record<string, unknown>>
      const experimenterUser = users.find((user) => user.email === experimenter.email)
      const approverUser = users.find((user) => user.email === approver.email)
      if (typeof experimenterUser?.id === 'string' && typeof approverUser?.id === 'string') {
        const groupsRes = await api('GET', '/api/v1/approver-groups', undefined, { authToken: adminAuth.token })
        const groups = arrayFrom(groupsRes.data, 'approver_groups') as Array<Record<string, unknown>>
        const existingGroup = groups.find((group) => group.experimenter_id === experimenterUser.id)
        const groupBody = { experimenter_id: experimenterUser.id, approver_ids: [approverUser.id], min_approvals: 1 }
        if (typeof existingGroup?.id === 'string') {
          await api('PATCH', `/api/v1/approver-groups/${existingGroup.id}`, groupBody, { authToken: adminAuth.token })
        } else {
          await api('POST', '/api/v1/approver-groups', groupBody, { authToken: adminAuth.token })
        }
      }
    }

    const experimenterAuth = await loginWithCredentials(experimenter)
    if (!experimenterAuth.token) {
      setScenarioRunning(false)
      return
    }
    await ensureDemoRuntimeCatalog(experimenterAuth.token, adminAuth.token || experimenterAuth.token)

    const flagsRes = await api('GET', '/api/v1/flags', undefined, { authToken: experimenterAuth.token })
    const flags = arrayFrom(flagsRes.data, 'flags') as FlagItem[]
    let flag: FlagItem | undefined = flags.find((item) => item.key === 'test_feature_flag') || flags[0]
    if (!flag?.id) {
      const createdFlag = await api('POST', '/api/v1/flags', { key: `gui_button_${stamp}`, value_type: 'string', default_value: 'control', owner: 'gui', description: 'Флаг быстрого сценария GUI' }, { authToken: experimenterAuth.token })
      flag = isRecord(createdFlag.data) ? createdFlag.data as FlagItem : undefined
    }
    const flagId = flag?.id || ''
    const flagKey = flag?.key || ''
    if (!flagId || !flagKey) {
      setScenarioRunning(false)
      return
    }

    const experiment = await api('POST', '/api/v1/experiments', {
      name: `GUI проверка ролей ${stamp}`,
      flag_id: flagId,
      audience_fraction: 0.5,
      metrics: [{ metric_key: 'demo_click_rate', metric_type: 'primary' }],
    }, { authToken: experimenterAuth.token })
    const experimentId = isRecord(experiment.data) && typeof experiment.data.id === 'string' ? experiment.data.id : ''
    if (!experimentId) {
      setScenarioRunning(false)
      await refreshAll(experimenterAuth.token)
      return
    }

    await api('POST', `/api/v1/experiments/${experimentId}/variants`, { variant_name: 'control', variant_value: 'control', weight: 0.25, is_control: true }, { authToken: experimenterAuth.token })
    await api('POST', `/api/v1/experiments/${experimentId}/variants`, { variant_name: 'treatment', variant_value: 'treatment', weight: 0.25, is_control: false }, { authToken: experimenterAuth.token })
    await api('PATCH', `/api/v1/experiments/${experimentId}/status`, { status: 'on_review', comment: 'GUI: экспериментатор отправил на ревью' }, { authToken: experimenterAuth.token })

    const approverAuth = await loginWithCredentials(approver)
    if (approverAuth.token) {
      await api('PATCH', `/api/v1/experiments/${experimentId}/status`, { status: 'approved', comment: 'GUI: аппрувер одобрил запуск' }, { authToken: approverAuth.token })
    }

    const experimenterAuth2 = await loginWithCredentials(experimenter)
    if (experimenterAuth2.token) {
      await api('PATCH', `/api/v1/experiments/${experimentId}/status`, { status: 'running', comment: 'GUI: экспериментатор запустил эксперимент' }, { authToken: experimenterAuth2.token })
    }

    const viewerAuth = await loginWithCredentials(viewer)
    if (viewerAuth.token) {
      const decision = await api('POST', '/api/v1/decide', { subject_id: 'gui-u42', attributes: { platform: 'web', country: 'RU' }, flags: [flagKey] }, { authToken: viewerAuth.token })
      const decisionId = findDecisionId(decision.data)
      if (decisionId) {
        updateDraft('event', { decision_id: decisionId, subject_id: 'gui-u42', event_type_key: 'demo_exposure' })
        await api('POST', '/api/v1/events', { events: [{ event_id: `gui-exposure-${stamp}`, decision_id: decisionId, event_type_key: 'demo_exposure', subject_id: 'gui-u42', timestamp: new Date().toISOString(), payload: { source: 'quick_scenario' } }] }, { authToken: viewerAuth.token })
        await api('POST', '/api/v1/events', { events: [{ event_id: `gui-click-${stamp}`, decision_id: decisionId, event_type_key: 'demo_click', subject_id: 'gui-u42', timestamp: new Date().toISOString(), payload: { source: 'quick_scenario' } }] }, { authToken: viewerAuth.token })
      }
      await api('GET', `/api/v1/experiments/${experimentId}/report?start=2026-02-01&end=2026-12-31&include_dynamics=true`, undefined, { authToken: viewerAuth.token })
    }

    updateDraft('report', { experiment_id: experimentId })
    updateDraft('status', { experiment_id: experimentId })
    updateDraft('variant', { experiment_id: experimentId })
    updateDraft('complete', { experiment_id: experimentId })
    updateDraft('learning', { experiment_id: experimentId })
    await refreshAll(viewerAuth.token || experimenterAuth.token, false, false)
    setScenarioRunning(false)
  }

  const prepareDemoExperiment = async () => {
    const stamp = demoStamp()
    const admin = accountPresets.find((account) => account.role === 'admin')!
    const experimenter = accountPresets.find((account) => account.role === 'experimenter')!
    const approver = accountPresets.find((account) => account.role === 'approver')!
    const viewer = accountPresets.find((account) => account.role === 'viewer')!

    const adminAuth = await loginWithCredentials(admin)
    if (adminAuth.token) {
      const usersRes = await api('GET', '/api/v1/users', undefined, { authToken: adminAuth.token })
      const users = arrayFrom(usersRes.data, 'users') as Array<Record<string, unknown>>
      const experimenterUser = users.find((user) => user.email === experimenter.email)
      const approverUser = users.find((user) => user.email === approver.email)
      if (typeof experimenterUser?.id === 'string' && typeof approverUser?.id === 'string') {
        const groupsRes = await api('GET', '/api/v1/approver-groups', undefined, { authToken: adminAuth.token })
        const groups = arrayFrom(groupsRes.data, 'approver_groups') as Array<Record<string, unknown>>
        const existingGroup = groups.find((group) => group.experimenter_id === experimenterUser.id)
        const groupBody = { experimenter_id: experimenterUser.id, approver_ids: [approverUser.id], min_approvals: 1 }
        if (typeof existingGroup?.id === 'string') {
          await api('PATCH', `/api/v1/approver-groups/${existingGroup.id}`, groupBody, { authToken: adminAuth.token })
        } else {
          await api('POST', '/api/v1/approver-groups', groupBody, { authToken: adminAuth.token })
        }
      }
    }

    const experimenterAuth = await loginWithCredentials(experimenter)
    if (!experimenterAuth.token) return { ok: false, flagKey: '', experimentId: '', message: 'Не удалось войти экспериментатором.' }
    await ensureDemoRuntimeCatalog(experimenterAuth.token, adminAuth.token || experimenterAuth.token)

    const demoFlagKey = `gui_demo_checkout_cta_${stamp}`
    const flagsRes = await api('GET', '/api/v1/flags', undefined, { authToken: experimenterAuth.token })
    const flags = arrayFrom(flagsRes.data, 'flags') as FlagItem[]
    let flag = flags.find((item) => item.key === demoFlagKey)
    if (!flag?.id) {
      const createdFlag = await api('POST', '/api/v1/flags', {
        key: demoFlagKey,
        value_type: 'string',
        default_value: 'control',
        owner: 'gui-demo',
        description: 'Флаг для наглядного демо A/B в GUI',
        metadata: { surface: 'checkout_demo' },
      }, { authToken: experimenterAuth.token })
      flag = isRecord(createdFlag.data) ? createdFlag.data as FlagItem : undefined
    }
    if (!flag?.id) return { ok: false, flagKey: demoFlagKey, experimentId: '', message: 'Не удалось создать demo-флаг.' }

    const experiment = await api('POST', '/api/v1/experiments', {
      name: `GUI demo checkout CTA ${stamp}`,
      flag_id: flag.id,
      audience_fraction: 1,
      targeting_rule: null,
      metrics: [{ metric_key: 'demo_click_rate', metric_type: 'primary' }],
    }, { authToken: experimenterAuth.token })
    const experimentId = isRecord(experiment.data) && typeof experiment.data.id === 'string' ? experiment.data.id : ''
    if (!experimentId) return { ok: false, flagKey: demoFlagKey, experimentId: '', message: 'Не удалось создать demo-эксперимент.' }

    await api('POST', `/api/v1/experiments/${experimentId}/variants`, { variant_name: 'control', variant_value: 'control', weight: 0.5, is_control: true }, { authToken: experimenterAuth.token })
    await api('POST', `/api/v1/experiments/${experimentId}/variants`, { variant_name: 'treatment', variant_value: 'treatment', weight: 0.5, is_control: false }, { authToken: experimenterAuth.token })
    await api('PATCH', `/api/v1/experiments/${experimentId}/status`, { status: 'on_review', comment: 'GUI demo: отправлено на ревью' }, { authToken: experimenterAuth.token })

    const approverAuth = await loginWithCredentials(approver)
    if (approverAuth.token) {
      await api('PATCH', `/api/v1/experiments/${experimentId}/status`, { status: 'approved', comment: 'GUI demo: одобрено' }, { authToken: approverAuth.token })
    }

    const experimenterAuth2 = await loginWithCredentials(experimenter)
    if (experimenterAuth2.token) {
      await api('PATCH', `/api/v1/experiments/${experimentId}/status`, { status: 'running', comment: 'GUI demo: запущено' }, { authToken: experimenterAuth2.token })
    }

    const viewerAuth = await loginWithCredentials(viewer)
    updateDraft('report', { experiment_id: experimentId, start: '2026-02-01', end: '2026-12-31' })
    updateDraft('decide', { flags: demoFlagKey })
    await refreshAll(viewerAuth.token || experimenterAuth.token, false, false)
    return { ok: true, flagKey: demoFlagKey, experimentId, message: 'Demo-эксперимент создан и запущен.' }
  }

  const module = useMemo(() => {
    const common = { api, catalogs, drafts, updateDraft, refreshAll, register }
    switch (active) {
      case 'overview':
        return (
          <Overview
            health={health}
            catalogs={catalogs}
            runningCount={runningCount}
            draftCount={draftCount}
            onRefresh={refreshAll}
            onScenario={runScenario}
            scenarioRunning={scenarioRunning}
            onNavigate={setActive}
          />
        )
      case 'access':
        return <AccessModule {...common} />
      case 'demo':
        return <AbDemoModule {...common} onOpenReports={() => setActive('reports')} onPrepareDemo={prepareDemoExperiment} />
      case 'catalog':
        return <CatalogModule {...common} />
      case 'flags':
        return <FlagsModule {...common} onOpenExperiment={() => setActive('experiments')} />
      case 'experiments':
        return <ExperimentsModule {...common} activeExperiment={activeExperiment} />
      case 'runtime':
        return <RuntimeModule {...common} />
      case 'reports':
        return <ReportsModule {...common} />
      case 'safety':
        return <SafetyModule {...common} />
      case 'learnings':
        return <LearningsModule {...common} />
      case 'conflicts':
        return <ConflictsModule {...common} />
      case 'ramp':
        return <RampModule {...common} />
      case 'raw':
        return <RawModule {...common} />
      default:
        return null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, health, catalogs, drafts, logs, busy, scenarioRunning])

  return (
    <div className="app-shell container-fluid p-0">
      <aside className="sidebar d-flex flex-column">
        <div className="brand">
          <div className="brand-mark">AB</div>
          <div>
            <strong>LOTTY</strong>
            <span>A/B Platform GUI</span>
          </div>
        </div>
        <nav className="nav flex-column">
          {nav.map((item) => {
            const Icon = item.icon
            return (
              <button key={item.id} className={active === item.id ? 'nav-item active' : 'nav-item'} onClick={() => setActive(item.id)} title={item.label}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar navbar">
          <div className="connection">
            <label>
              Адрес backend
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
              <span className="field-help">Обычно /__api: Vite проксирует в localhost:8080</span>
            </label>
            <form className="login-form" onSubmit={login}>
              <label>
                Аккаунт
                <select value={selectedAccount} onChange={(event) => applyAccountPreset(event.target.value)}>
                  {accountPresets.map((account) => (
                    <option key={account.id} value={account.id}>{account.label}</option>
                  ))}
                </select>
              </label>
              <label>
                Почта
                <input value={email} onChange={(event) => setEmail(event.target.value)} />
              </label>
              <label>
                Пароль
                <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
              </label>
              <button className="primary btn btn-primary" disabled={busy} title="Авторизоваться">
                <KeyRound size={16} />
                Войти
              </button>
            </form>
            <div className="role-hint">
              <strong>{selectedPreset.label}</strong>
              <span>{selectedPreset.note} · role: {selectedPreset.role}</span>
            </div>
          </div>
          <div className="top-actions">
            <StatusDot label="health" state={health.health} />
            <StatusDot label="ready" state={health.ready} />
            <button className="secondary success btn btn-outline-success" onClick={() => refreshAll()} disabled={busy} title="Обновить справочники">
              <RefreshCw size={16} />
              Обновить данные
            </button>
          </div>
        </header>

        <section className="workspace row g-3">
          <div className="module col">{module}</div>
          <Inspector log={lastLog} logs={logs} token={token} currentUser={currentUser} onClear={() => setLogs([])} />
        </section>
      </main>
    </div>
  )
}

type ModuleProps = {
  api: (method: HttpMethod, path: string, body?: unknown) => Promise<ApiResult>
  catalogs: Catalogs
  drafts: Drafts
  updateDraft: <K extends keyof Drafts>(section: K, patch: Partial<Drafts[K]>) => void
  refreshAll: () => Promise<void>
  register: (payload: { email: string; first_name: string; password: string }) => Promise<void>
}

function Overview({ health, catalogs, runningCount, draftCount, onRefresh, onScenario, scenarioRunning, onNavigate }: {
  health: HealthState
  catalogs: Catalogs
  runningCount: number
  draftCount: number
  onRefresh: () => void
  onScenario: () => void
  scenarioRunning: boolean
  onNavigate: (section: (typeof nav)[number]['id']) => void
}) {
  return (
    <>
      <ModuleHeader
        title="Проверка A/B backend"
        description="Начните с готового сценария или выберите роль сверху. Интерфейс сам подставляет тестовые логины и показывает, какие действия доступны каждой роли."
        actions={
          <>
            <button className="secondary success" onClick={onRefresh}><RefreshCw size={16} />Обновить данные</button>
            <button className="primary" onClick={onScenario} disabled={scenarioRunning}><Play size={16} />Быстрый сценарий по ролям</button>
          </>
        }
      />
      <section className="starter-panel">
        <div>
          <span className="eyebrow">Если пока непонятно, что нажимать</span>
          <h2>Проверьте backend как готовый продукт за 3 шага</h2>
          <p>GUI работает поверх реального API на localhost:8080: выбираете роль, выполняете действие, смотрите HTTP-запрос и ответ справа.</p>
        </div>
        <div className="starter-actions">
          <button className="primary" onClick={onScenario} disabled={scenarioRunning}><Play size={16} />Запустить полный сценарий</button>
          <button className="secondary success" onClick={() => onNavigate('demo')}><Play size={16} />Открыть живое демо</button>
          <button className="secondary" onClick={() => onNavigate('experiments')}><FlaskConical size={16} />Открыть эксперименты</button>
          <button className="secondary" onClick={() => onNavigate('reports')}><BarChart3 size={16} />Посмотреть отчёты</button>
        </div>
      </section>
      <div className="guide-grid">
        <GuideCard step="1" title="Выберите аккаунт" text="Сверху есть готовые роли: админ управляет пользователями, экспериментатор создаёт флаги и эксперименты, approver одобряет, viewer проверяет runtime и отчёты." />
        <GuideCard step="2" title="Нажмите главное действие" text="В каждом разделе первая форма делает основной запрос. Таблицы ниже помогают выбрать ID без ручного копирования." />
        <GuideCard step="3" title="Смотрите справа" text="Инспектор API показывает body, статус и ответ. Старые запросы можно открыть кликом, а новый запрос снова откроется автоматически." />
      </div>
      <div className="stats-grid">
        <Stat icon={<Activity />} label="Health" value={health.health === 'ok' ? 'ok' : 'нет ответа'} tone={health.health === 'ok' ? 'good' : 'bad'} />
        <Stat icon={<Flag />} label="Флаги" value={catalogs.flags.length} />
        <Stat icon={<FlaskConical />} label="Эксперименты" value={catalogs.experiments.length} />
        <Stat icon={<CheckCircle2 />} label="Запущены" value={runningCount} tone="good" />
        <Stat icon={<ClipboardCheck />} label="Черновики" value={draftCount} tone="warn" />
        <Stat icon={<BookOpen />} label="Выводы" value={catalogs.learnings.length} />
      </div>
      <section className="panel">
        <div className="panel-title">
          <h2>Кто что делает</h2>
          <span>быстрый сценарий сам переключает роли</span>
        </div>
        <div className="role-grid">
          {accountPresets.slice(0, 4).map((account) => (
            <div className="role-card" key={account.id}>
              <strong>{account.label}</strong>
              <code>{account.email}</code>
              <span>{account.note}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="panel-title">
          <h2>Жизненный цикл</h2>
          <span>черновик → ревью → одобрено → запущен → завершён → архив</span>
        </div>
        <div className="status-lane">
          {statuses.map((status) => (
            <div key={status} className="status-step">
              <span>{statusLabel(status)}</span>
              <strong>{catalogs.experiments.filter((item) => item.status === status).length}</strong>
            </div>
          ))}
        </div>
      </section>
      <DataTable
        title="Последние эксперименты"
        rows={catalogs.experiments.slice(0, 8)}
        columns={['name', 'status', 'flag_key', 'audience_fraction', 'id']}
        empty="После логина и обновления данных здесь появятся эксперименты."
      />
    </>
  )
}

function AccessModule({ api, catalogs, drafts, updateDraft, refreshAll, register }: ModuleProps) {
  const d = drafts
  return (
    <>
      <ModuleHeader title="Доступ и ревью" description="Регистрация, роли, пользователи и approver-группы перед запуском экспериментов." />
      <div className="two-col">
        <FormCard
          title="Регистрация нового аккаунта"
          submitLabel="Зарегистрироваться"
          icon={<UserPlus size={16} />}
          tone="success"
          defaultOpen
          onSubmit={async () => {
            await register({
              email: d.register.email,
              first_name: d.register.first_name,
              password: d.register.password,
            })
          }}
        >
          <div className="helper-strip success">
            POST /api/v1/register создаёт аккаунт и сразу возвращает JWT, поэтому после успеха GUI сам переключится на нового пользователя.
          </div>
          <TextInput label="Email" value={d.register.email} onChange={(v) => updateDraft('register', { email: v })} />
          <TextInput label="Имя" value={d.register.first_name} onChange={(v) => updateDraft('register', { first_name: v })} />
          <TextInput label="Пароль" type="password" value={d.register.password} onChange={(v) => updateDraft('register', { password: v })} />
        </FormCard>
        <FormCard
          title="Создать пользователя"
          submitLabel="Создать пользователя"
          icon={<UserPlus size={16} />}
          tone="success"
          onSubmit={async () => {
            await api('POST', '/api/v1/users', clean({
              email: d.user.email,
              first_name: d.user.first_name,
              password: d.user.password,
              role: d.user.role,
            }))
            await refreshAll()
          }}
        >
          <TextInput label="Email" value={d.user.email} onChange={(v) => updateDraft('user', { email: v })} />
          <TextInput label="Имя" value={d.user.first_name} onChange={(v) => updateDraft('user', { first_name: v })} />
          <TextInput label="Пароль" type="password" value={d.user.password} onChange={(v) => updateDraft('user', { password: v })} />
          <SelectInput label="Роль" value={d.user.role} options={['admin', 'experimenter', 'approver', 'viewer']} onChange={(v) => updateDraft('user', { role: v })} />
        </FormCard>
        <FormCard
          title="Изменить пользователя"
          submitLabel="Сохранить пользователя"
          icon={<Edit3 size={16} />}
          tone="warning"
          onSubmit={async () => {
            await api('PATCH', `/api/v1/users/${d.user.id}`, clean({
              email: d.user.email,
              first_name: d.user.first_name,
              password: d.user.password,
              role: d.user.role,
            }))
            await refreshAll()
          }}
        >
          <TextInput label="User ID" value={d.user.id} onChange={(v) => updateDraft('user', { id: v })} />
          <TextInput label="Email" value={d.user.email} onChange={(v) => updateDraft('user', { email: v })} />
          <TextInput label="Имя" value={d.user.first_name} onChange={(v) => updateDraft('user', { first_name: v })} />
          <TextInput label="Новый пароль" type="password" value={d.user.password} onChange={(v) => updateDraft('user', { password: v })} />
          <SelectInput label="Роль" value={d.user.role} options={['admin', 'experimenter', 'approver', 'viewer']} onChange={(v) => updateDraft('user', { role: v })} />
        </FormCard>
        <FormCard
          title="Approver group"
          submitLabel="Сохранить группу"
          icon={<ClipboardCheck size={16} />}
          tone="primary"
          onSubmit={async () => {
            await api('POST', '/api/v1/approver-groups', {
              experimenter_id: d.approverGroup.experimenter_id || null,
              approver_ids: splitCsv(d.approverGroup.approver_ids),
              min_approvals: Number(d.approverGroup.min_approvals),
            })
            await refreshAll()
          }}
        >
          <TextInput label="Experimenter ID или пусто для default" value={d.approverGroup.experimenter_id} onChange={(v) => updateDraft('approverGroup', { experimenter_id: v })} />
          <TextInput label="Approver IDs через запятую" value={d.approverGroup.approver_ids} onChange={(v) => updateDraft('approverGroup', { approver_ids: v })} />
          <NumberInput label="Минимум одобрений" value={d.approverGroup.min_approvals} onChange={(v) => updateDraft('approverGroup', { min_approvals: v })} />
        </FormCard>
      </div>
      <DataTable
        title="Пользователи"
        rows={catalogs.users}
        columns={['email', 'first_name', 'role', 'id']}
        empty="Войдите администратором и обновите данные."
        actions={(row) => (
          <button className="mini" onClick={() => updateDraft('user', {
            id: String(row.id || ''),
            email: String(row.email || ''),
            first_name: String(row.first_name || ''),
            role: String(row.role || 'viewer'),
            password: '',
          })}><Edit3 size={14} />редактировать</button>
        )}
      />
      <DataTable title="Approver groups" rows={catalogs.approverGroups} columns={['experimenter_id', 'approver_ids', 'min_approvals', 'id']} empty="Группы approver-ов появятся после входа администратором." />
    </>
  )
}

function CatalogModule({ api, catalogs, drafts, updateDraft, refreshAll }: ModuleProps) {
  const d = drafts
  return (
    <>
      <ModuleHeader title="Каталоги событий и метрик" description="Метрики декларативно описывают, какие события считать и как агрегировать отчёты." />
      <div className="two-col">
        <FormCard
          title="Event type"
          submitLabel="Создать event type"
          onSubmit={async () => {
            await api('POST', '/api/v1/event-types', clean({
              ...d.eventType,
              required_params: parseJson(d.eventType.required_params),
              requires_show_event_type_id: d.eventType.requires_show_event_type_id || null,
            }))
            await refreshAll()
          }}
        >
          <TextInput label="Key" value={d.eventType.key} onChange={(v) => updateDraft('eventType', { key: v })} />
          <TextInput label="Название" value={d.eventType.display_name} onChange={(v) => updateDraft('eventType', { display_name: v })} />
          <TextInput label="Описание" value={d.eventType.description} onChange={(v) => updateDraft('eventType', { description: v })} />
          <Toggle label="Critical" checked={d.eventType.is_critical} onChange={(v) => updateDraft('eventType', { is_critical: v })} />
          <JsonArea label="Required params" value={d.eventType.required_params} onChange={(v) => updateDraft('eventType', { required_params: v })} />
        </FormCard>
        <FormCard
          title="Metric"
          submitLabel="Создать метрику"
          onSubmit={async () => {
            await api('POST', '/api/v1/metrics', clean({
              key: d.metric.key,
              name: d.metric.name,
              unit: d.metric.unit || null,
              description: d.metric.description || null,
              aggregation_rule: parseJson(d.metric.aggregation_rule),
              event_expectations: parseJson(d.metric.event_expectations),
              attribution_rule: parseJson(d.metric.attribution_rule),
            }))
            await refreshAll()
          }}
        >
          <TextInput label="Key" value={d.metric.key} onChange={(v) => updateDraft('metric', { key: v })} />
          <TextInput label="Название" value={d.metric.name} onChange={(v) => updateDraft('metric', { name: v })} />
          <TextInput label="Unit" value={d.metric.unit} onChange={(v) => updateDraft('metric', { unit: v })} />
          <JsonArea label="Aggregation rule" value={d.metric.aggregation_rule} onChange={(v) => updateDraft('metric', { aggregation_rule: v })} />
          <JsonArea label="Event expectations" value={d.metric.event_expectations} onChange={(v) => updateDraft('metric', { event_expectations: v })} />
        </FormCard>
      </div>
      <DataTable title="Event types" rows={catalogs.eventTypes} columns={['key', 'display_name', 'is_critical', 'status', 'id']} empty="Каталог событий пуст." />
      <DataTable title="Metrics" rows={catalogs.metrics} columns={['key', 'name', 'unit', 'description', 'id']} empty="Каталог метрик пуст." />
    </>
  )
}

function FlagsModule({ api, catalogs, drafts, updateDraft, refreshAll, onOpenExperiment }: ModuleProps & { onOpenExperiment: () => void }) {
  const d = drafts.flag
  return (
    <>
      <ModuleHeader title="Фича-флаги" description="Флаг хранит ключ, тип значения и значение по умолчанию, которое вернётся без активного эксперимента." />
      <FormCard
        title="Создать флаг"
        submitLabel="Создать флаг"
        wide
        onSubmit={async () => {
          await api('POST', '/api/v1/flags', clean({ ...d, metadata: parseJson(d.metadata), owner: d.owner || null, description: d.description || null }))
          await refreshAll()
        }}
      >
        <div className="form-grid">
          <TextInput label="Key" value={d.key} onChange={(v) => updateDraft('flag', { key: v })} />
          <SelectInput label="Тип значения" value={d.value_type} options={['string', 'number', 'bool']} onChange={(v) => updateDraft('flag', { value_type: v })} />
          <TextInput label="Значение по умолчанию" value={d.default_value} onChange={(v) => updateDraft('flag', { default_value: v })} />
          <TextInput label="Владелец" value={d.owner} onChange={(v) => updateDraft('flag', { owner: v })} />
        </div>
        <TextInput label="Описание" value={d.description} onChange={(v) => updateDraft('flag', { description: v })} />
        <JsonArea label="Metadata" value={d.metadata} onChange={(v) => updateDraft('flag', { metadata: v })} />
      </FormCard>
      <DataTable
        title="Флаги"
        rows={catalogs.flags}
        columns={['key', 'value_type', 'default_value', 'owner', 'id']}
        empty="Создайте флаг или обновите данные после логина."
        actions={(row) => (
          <button className="mini" onClick={() => {
            updateDraft('experiment', { flag_id: String(row.id || '') })
            onOpenExperiment()
          }}>создать эксперимент</button>
        )}
      />
    </>
  )
}

function ExperimentsModule({ api, catalogs, drafts, updateDraft, refreshAll, activeExperiment }: ModuleProps & { activeExperiment?: ExperimentItem }) {
  const d = drafts
  return (
    <>
      <ModuleHeader title="Эксперименты и жизненный цикл" description="Создание, варианты, ревью-статусы, завершение и архивирование. Веса вариантов должны суммарно соответствовать доле аудитории." />
      <div className="two-col">
        <FormCard
          title="Создать эксперимент"
          submitLabel="Создать эксперимент"
          onSubmit={async () => {
            await api('POST', '/api/v1/experiments', clean({
              name: d.experiment.name,
              flag_id: d.experiment.flag_id,
              audience_fraction: Number(d.experiment.audience_fraction),
              targeting_rule: d.experiment.targeting_rule || null,
              metrics: parseJson(d.experiment.metrics),
            }))
            await refreshAll()
          }}
        >
          <TextInput label="Название" value={d.experiment.name} onChange={(v) => updateDraft('experiment', { name: v })} />
          <SelectInput label="Флаг" value={d.experiment.flag_id} options={catalogs.flags.map((f) => ({ value: f.id || '', label: `${f.key} ${f.id ? `(${short(f.id)})` : ''}` }))} onChange={(v) => updateDraft('experiment', { flag_id: v })} />
          <NumberInput label="Доля аудитории" value={d.experiment.audience_fraction} step={0.05} onChange={(v) => updateDraft('experiment', { audience_fraction: v })} />
          <TextInput label="Правило таргетинга" value={d.experiment.targeting_rule} onChange={(v) => updateDraft('experiment', { targeting_rule: v })} />
          <JsonArea label="Метрики" value={d.experiment.metrics} onChange={(v) => updateDraft('experiment', { metrics: v })} />
        </FormCard>
        <FormCard
          title="Добавить вариант"
          submitLabel="Добавить вариант"
          onSubmit={async () => {
            await api('POST', `/api/v1/experiments/${d.variant.experiment_id}/variants`, clean({
              variant_name: d.variant.variant_name,
              variant_value: d.variant.variant_value,
              weight: Number(d.variant.weight),
              is_control: d.variant.is_control,
            }))
            await refreshAll()
          }}
        >
          <SelectInput label="Эксперимент" value={d.variant.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('variant', { experiment_id: v })} />
          <TextInput label="Название варианта" value={d.variant.variant_name} onChange={(v) => updateDraft('variant', { variant_name: v })} />
          <TextInput label="Значение варианта" value={d.variant.variant_value} onChange={(v) => updateDraft('variant', { variant_value: v })} />
          <NumberInput label="Вес" value={d.variant.weight} step={0.05} onChange={(v) => updateDraft('variant', { weight: v })} />
          <Toggle label="Контрольный" checked={d.variant.is_control} onChange={(v) => updateDraft('variant', { is_control: v })} />
        </FormCard>
      </div>
      <div className="two-col">
        <FormCard
          title="Сменить статус"
          submitLabel="Сменить статус"
          onSubmit={async () => {
            await api('PATCH', `/api/v1/experiments/${d.status.experiment_id}/status`, { status: d.status.status, comment: d.status.comment || null })
            await refreshAll()
          }}
        >
          <SelectInput label="Эксперимент" value={d.status.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('status', { experiment_id: v })} />
          <SelectInput label="Статус" value={d.status.status} options={['draft', 'on_review', 'approved', 'running', 'paused', 'rejected', 'archived'].map((status) => ({ value: status, label: statusLabel(status) }))} onChange={(v) => updateDraft('status', { status: v })} />
          <TextInput label="Комментарий" value={d.status.comment} onChange={(v) => updateDraft('status', { comment: v })} />
        </FormCard>
        <FormCard
          title="Завершить эксперимент"
          submitLabel="Завершить"
          onSubmit={async () => {
            await api('POST', `/api/v1/experiments/${d.complete.experiment_id}/complete`, clean({
              completion_outcome: d.complete.completion_outcome,
              completion_winner_variant_id: d.complete.completion_winner_variant_id || null,
              comment: d.complete.comment,
            }))
            await refreshAll()
          }}
        >
          <SelectInput label="Эксперимент" value={d.complete.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('complete', { experiment_id: v })} />
          <SelectInput label="Исход" value={d.complete.completion_outcome} options={[{ value: 'rollout_winner', label: 'Раскатить победителя' }, { value: 'rollback', label: 'Откатить' }, { value: 'no_effect', label: 'Эффект не найден' }]} onChange={(v) => updateDraft('complete', { completion_outcome: v })} />
          <TextInput label="ID варианта-победителя" value={d.complete.completion_winner_variant_id} onChange={(v) => updateDraft('complete', { completion_winner_variant_id: v })} />
          <TextInput label="Комментарий" value={d.complete.comment} onChange={(v) => updateDraft('complete', { comment: v })} />
        </FormCard>
      </div>
      {activeExperiment && (
        <section className="panel">
          <div className="panel-title"><h2>Выбранный эксперимент</h2><span>{activeExperiment.name}</span></div>
          <pre className="json-inline">{pretty(activeExperiment)}</pre>
        </section>
      )}
      <DataTable
        title="Эксперименты"
        rows={catalogs.experiments}
        columns={['name', 'status', 'flag_key', 'audience_fraction', 'id']}
        empty="Экспериментов пока нет."
        actions={(row) => (
          <div className="row-actions">
              <button className="mini" onClick={() => {
              const id = String(row.id || '')
              updateDraft('variant', { experiment_id: id })
              updateDraft('status', { experiment_id: id })
              updateDraft('report', { experiment_id: id })
              updateDraft('complete', { experiment_id: id })
              updateDraft('learning', { experiment_id: id })
            }}>выбрать</button>
            <button className="mini danger" onClick={() => api('POST', `/api/v1/experiments/${row.id}/archive`).then(() => refreshAll())}><Archive size={14} />архивировать</button>
          </div>
        )}
      />
    </>
  )
}

function RuntimeModule({ api, catalogs, drafts, updateDraft }: ModuleProps) {
  const d = drafts
  return (
    <>
      <ModuleHeader title="Выдача решений и события" description="Проверка закрепления варианта, fallback на default, decision_id, дедупликации и атрибуции событий." />
      <div className="two-col">
        <FormCard
          title="Выдать решение"
          submitLabel="Получить решение"
          onSubmit={async () => {
            const res = await api('POST', '/api/v1/decide', { subject_id: d.decide.subject_id, attributes: parseJson(d.decide.attributes), flags: splitCsv(d.decide.flags) })
            const decisionId = findDecisionId(res.data)
            if (decisionId) updateDraft('event', { decision_id: decisionId, subject_id: d.decide.subject_id })
          }}
        >
          <TextInput label="ID субъекта" value={d.decide.subject_id} onChange={(v) => updateDraft('decide', { subject_id: v })} />
          <TextInput label="Flags через запятую" value={d.decide.flags} onChange={(v) => updateDraft('decide', { flags: v })} />
          <JsonArea label="Attributes" value={d.decide.attributes} onChange={(v) => updateDraft('decide', { attributes: v })} />
        </FormCard>
        <FormCard
          title="Отправить событие"
          submitLabel="Отправить событие"
          onSubmit={async () => {
            await api('POST', '/api/v1/events', { events: [{ event_id: `gui-${crypto.randomUUID()}`, decision_id: d.event.decision_id, event_type_key: d.event.event_type_key, subject_id: d.event.subject_id, timestamp: new Date().toISOString(), payload: parseJson(d.event.payload) }] })
          }}
        >
          <TextInput label="Decision ID" value={d.event.decision_id} onChange={(v) => updateDraft('event', { decision_id: v })} />
          <TextInput label="ID субъекта" value={d.event.subject_id} onChange={(v) => updateDraft('event', { subject_id: v })} />
          <SelectInput label="Тип события" value={d.event.event_type_key} options={catalogs.eventTypes.map((x) => String(x.key || '')).filter(Boolean)} onChange={(v) => updateDraft('event', { event_type_key: v })} />
          <JsonArea label="Payload" value={d.event.payload} onChange={(v) => updateDraft('event', { payload: v })} />
        </FormCard>
      </div>
      <DataTable title="Доступные флаги для decide" rows={catalogs.flags} columns={['key', 'default_value', 'value_type', 'id']} empty="Флаги не загружены." />
    </>
  )
}

function AbDemoModule({ api, catalogs, updateDraft, onOpenReports, onPrepareDemo }: ModuleProps & { onOpenReports: () => void; onPrepareDemo: () => Promise<{ ok: boolean; flagKey: string; experimentId: string; message: string }> }) {
  const defaultFlag = catalogs.flags.find((flag) => flag.key === 'gui_demo_checkout_cta')?.key || catalogs.flags.find((flag) => flag.key === 'test_feature_flag')?.key || catalogs.flags[0]?.key || 'gui_demo_checkout_cta'
  const [subjectId, setSubjectId] = useState(`shopper-${Math.floor(Math.random() * 9000 + 1000)}`)
  const [flagKey, setFlagKey] = useState(defaultFlag)
  const [preparedFlagKeys, setPreparedFlagKeys] = useState<string[]>([])
  const [assignment, setAssignment] = useState<Record<string, unknown> | null>(null)
  const [demoLog, setDemoLog] = useState<string[]>(['Нажмите “Подготовить демо”, чтобы создать отдельный running-эксперимент для этого экрана.'])
  const [preparing, setPreparing] = useState(false)
  const [trafficRunning, setTrafficRunning] = useState(false)

  useEffect(() => {
    if (!flagKey && defaultFlag) setFlagKey(defaultFlag)
  }, [defaultFlag, flagKey])

  const decisionId = assignment ? String(assignment.decision_id || '') : ''
  const variantName = assignment ? String(assignment.variant_name || assignment.value || 'default') : 'ещё не назначен'
  const variantValue = assignment ? String(assignment.variant_value || assignment.value || variantName).toLowerCase() : ''
  const isTreatment = /treatment|blue|premium|new|variant|b|test/.test(variantValue) || /treatment|вариант b/i.test(variantName)
  const theme = assignment ? isTreatment ? 'treatment' : 'control' : 'idle'
  const flagOptions = Array.from(new Set([...preparedFlagKeys, ...catalogs.flags.map((flag) => flag.key).filter(Boolean), flagKey].filter(Boolean)))

  const appendDemoLog = (message: string) => setDemoLog((prev) => [message, ...prev].slice(0, 6))

  const prepareDemo = async () => {
    setPreparing(true)
    try {
      const result = await onPrepareDemo()
      if (result.flagKey) {
        setPreparedFlagKeys((prev) => Array.from(new Set([result.flagKey, ...prev])))
        setFlagKey(result.flagKey)
      }
      setAssignment(null)
      appendDemoLog(result.message)
      if (result.ok) appendDemoLog('Теперь нажмите “Получить вариант”: default больше не должен приходить, если эксперимент running.')
    } finally {
      setPreparing(false)
    }
  }

  const getDecision = async () => {
    const res = await api('POST', '/api/v1/decide', {
      subject_id: subjectId,
      attributes: { country: 'RU', platform: 'web', surface: 'checkout_demo' },
      flags: [flagKey],
    })
    const nextAssignment = findDecisionAssignment(res.data)
    if (res.ok && nextAssignment) {
      setAssignment(nextAssignment)
      const nextDecisionId = String(nextAssignment.decision_id || '')
      const experimentId = String(nextAssignment.experiment_id || '')
      if (experimentId) updateDraft('report', { experiment_id: experimentId })
      appendDemoLog(`Backend назначил вариант: ${nextAssignment.variant_name || nextAssignment.value || 'default'}`)
      if (nextDecisionId) {
        await api('POST', '/api/v1/events', {
          events: [{
            event_id: `gui-demo-exposure-${crypto.randomUUID()}`,
            decision_id: nextDecisionId,
            event_type_key: 'demo_exposure',
            subject_id: subjectId,
            timestamp: new Date().toISOString(),
            payload: { surface: 'checkout_demo', flag_key: flagKey },
          }],
        })
        appendDemoLog('Отправили demo_exposure: пользователь увидел вариант.')
      }
    } else {
      appendDemoLog('Backend не вернул назначение. Нажмите “Подготовить демо” или проверьте viewer token.')
    }
    if (res.ok && nextAssignment && String(nextAssignment.value || nextAssignment.variant_name || '').toLowerCase() === 'default') {
      appendDemoLog('Пришёл default: для выбранного флага нет подходящего running-эксперимента или пользователь не попал в аудиторию.')
    }
  }

  const sendConversion = async () => {
    if (!decisionId) {
      appendDemoLog('Сначала получите вариант, чтобы появился decision_id.')
      return
    }
    await api('POST', '/api/v1/events', {
      events: [{
        event_id: `gui-demo-click-${crypto.randomUUID()}`,
        decision_id: decisionId,
        event_type_key: 'demo_click',
        subject_id: subjectId,
        timestamp: new Date().toISOString(),
        payload: { surface: 'checkout_demo', cta_theme: theme, flag_key: flagKey },
      }],
    })
    appendDemoLog('Отправили demo_click: это клик для demo_click_rate в отчёте.')
  }

  const generateDemoTraffic = async () => {
    setTrafficRunning(true)
    try {
      let treatmentClicks = 0
      let controlClicks = 0
      let exposures = 0
      let reportExperimentId = ''
      const batchId = crypto.randomUUID().slice(0, 8)
      for (let index = 0; index < 18; index += 1) {
        const nextSubjectId = `demo-${batchId}-${index}`
        const decision = await api('POST', '/api/v1/decide', {
          subject_id: nextSubjectId,
          attributes: { country: 'RU', platform: 'web', surface: 'checkout_demo', source: 'generated_demo_traffic' },
          flags: [flagKey],
        })
        const nextAssignment = findDecisionAssignment(decision.data)
        const nextDecisionId = findDecisionId(decision.data)
        const variant = String(nextAssignment?.variant_name || nextAssignment?.value || '').toLowerCase()
        if (!nextDecisionId || !nextAssignment) continue
        reportExperimentId = String(nextAssignment.experiment_id || reportExperimentId)
        const shouldClick = variant === 'treatment' || (variant === 'control' && index % 6 === 0)
        const events = [{
          event_id: `gui-demo-traffic-exposure-${crypto.randomUUID()}`,
          decision_id: nextDecisionId,
          event_type_key: 'demo_exposure',
          subject_id: nextSubjectId,
          timestamp: new Date().toISOString(),
          payload: { source: 'generated_demo_traffic', variant },
        }]
        if (shouldClick) {
          events.push({
            event_id: `gui-demo-traffic-click-${crypto.randomUUID()}`,
            decision_id: nextDecisionId,
            event_type_key: 'demo_click',
            subject_id: nextSubjectId,
            timestamp: new Date().toISOString(),
            payload: { source: 'generated_demo_traffic', variant },
          })
          if (variant === 'treatment') treatmentClicks += 1
          if (variant === 'control') controlClicks += 1
        }
        exposures += 1
        await api('POST', '/api/v1/events', { events })
      }
      if (reportExperimentId) updateDraft('report', { experiment_id: reportExperimentId })
      appendDemoLog(`Сгенерировали трафик: ${exposures} exposure, treatment clicks ${treatmentClicks}, control clicks ${controlClicks}.`)
    } finally {
      setTrafficRunning(false)
    }
  }

  return (
    <>
      <ModuleHeader
        title="Наглядное демо A/B"
        description="Мини-продукт получает вариант через /decide, реально меняет интерфейс и отправляет события в backend. Так видно, как автоматическое A/B-тестирование работает для пользователя."
      />
      <section className="demo-shell">
        <div className={`demo-product ${theme}`}>
          <div className="demo-product-top">
            <span>Checkout demo</span>
            <strong>{assignment ? `Вариант: ${variantName}` : 'Пользователь ещё не зашёл'}</strong>
          </div>
          {assignment ? (
            <>
              <div className="demo-offer">
                <span className="demo-badge">{theme === 'treatment' ? 'Новый вариант' : 'Контроль'}</span>
                <h2>{theme === 'treatment' ? 'Быстрая покупка с ярким CTA' : 'Классическая карточка покупки'}</h2>
                <p>{theme === 'treatment' ? 'Backend назначил экспериментальный вариант: кнопка заметнее, текст увереннее, акцент сильнее.' : 'Контрольный вариант спокойнее: привычный текст, сдержанный акцент, базовая компоновка.'}</p>
                <button className="demo-cta" onClick={sendConversion}>{theme === 'treatment' ? 'Купить сейчас' : 'Добавить в корзину'}</button>
              </div>
              <div className="demo-receipt">
                <div><span>Subject</span><strong>{subjectId}</strong></div>
                <div><span>Flag</span><strong>{flagKey}</strong></div>
                <div><span>Decision ID</span><strong>{decisionId ? short(decisionId) : '—'}</strong></div>
              </div>
            </>
          ) : (
            <div className="demo-empty-site">
              <span>Сайт ещё не открыт</span>
              <h2>Пользователь не видел страницу, поэтому варианта пока нет</h2>
              <p>Нажмите запуск ниже: GUI вызовет /decide, backend назначит control или treatment, и только после этого появится реальный экран сайта.</p>
              <button className="demo-cta" onClick={getDecision}><Play size={16} />Запустить визит пользователя</button>
            </div>
          )}
        </div>
        <div className="demo-control">
          <div className="panel-title"><h2>Как запустить</h2><span>реальные API-вызовы</span></div>
          <div className="demo-fields">
            <TextInput label="Subject ID" value={subjectId} onChange={(value) => {
              setSubjectId(value)
              setAssignment(null)
            }} />
            <SelectInput label="Флаг" value={flagKey} options={flagOptions} onChange={(value) => {
              setFlagKey(value)
              setAssignment(null)
            }} />
          </div>
          <div className="button-row">
            <button className="secondary" onClick={prepareDemo} disabled={preparing}><RefreshCw size={16} />{preparing ? 'Готовлю демо...' : 'Подготовить демо'}</button>
            <button className="primary" onClick={getDecision}><Play size={16} />Получить вариант</button>
            <button className="secondary" onClick={() => {
              setSubjectId(`shopper-${Math.floor(Math.random() * 9000 + 1000)}`)
              setAssignment(null)
              appendDemoLog('Сгенерировали нового пользователя. Можно получить другой вариант.')
            }}>Новый пользователь</button>
            <button className="secondary" onClick={generateDemoTraffic} disabled={trafficRunning}>{trafficRunning ? 'Генерирую...' : 'Сгенерировать трафик'}</button>
            <button className="secondary" onClick={onOpenReports}><BarChart3 size={16} />Открыть отчёт</button>
          </div>
          <div className="demo-flow">
            <div className={assignment ? 'done' : ''}><strong>1</strong><span>/decide назначает вариант</span></div>
            <div className={assignment ? 'done' : ''}><strong>2</strong><span>UI меняется для пользователя</span></div>
            <div className={decisionId ? 'done' : ''}><strong>3</strong><span>/events пишет exposure и click</span></div>
            <div><strong>4</strong><span>/report считает click_rate</span></div>
          </div>
          <div className="demo-log">
            {demoLog.map((item, index) => <p key={index}>{item}</p>)}
          </div>
        </div>
      </section>
    </>
  )
}

function ReportsModule({ api, catalogs, drafts, updateDraft }: ModuleProps) {
  const d = drafts.report
  const [report, setReport] = useState<unknown>(null)
  return (
    <>
      <ModuleHeader title="Отчёты" description="Отчёт показывает варианты, события, значения метрик, сводку по основной метрике и финальный результат." />
      <FormCard
        title="Отчёт по эксперименту"
        wide
        submitLabel="Построить отчёт"
        onSubmit={async () => {
          const res = await api('GET', `/api/v1/experiments/${d.experiment_id}/report?start=${encodeURIComponent(d.start)}&end=${encodeURIComponent(d.end)}&include_dynamics=${d.include_dynamics}`)
          if (res.ok) setReport(res.data)
        }}
      >
        <div className="form-grid">
          <SelectInput label="Эксперимент" value={d.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('report', { experiment_id: v })} />
          <TextInput label="Начало" value={d.start} onChange={(v) => updateDraft('report', { start: v })} />
          <TextInput label="Конец" value={d.end} onChange={(v) => updateDraft('report', { end: v })} />
          <Toggle label="Динамика" checked={d.include_dynamics} onChange={(v) => updateDraft('report', { include_dynamics: v })} />
        </div>
      </FormCard>
      <ReportView report={report} />
      <DataTable title="Метрики каталога" rows={catalogs.metrics} columns={['key', 'name', 'unit', 'description']} empty="Каталог метрик пуст или текущая роль не может его прочитать." />
    </>
  )
}

function ReportView({ report }: { report: unknown }) {
  if (!report) {
    return <section className="panel"><div className="empty-note">Постройте отчёт, и здесь появятся варианты, метрики, сводка и dynamics из ответа backend.</div></section>
  }
  const summary = isRecord(report) && isRecord(report.primary_metric_summary) ? report.primary_metric_summary : null
  const summaryLines = summary && Array.isArray(summary.summary_lines) ? summary.summary_lines : []
  const variants = isRecord(report) ? arrayFrom(report, 'variants') as Array<Record<string, unknown>> : []
  const metrics = isRecord(report) ? arrayFrom(report, 'metrics') as Array<Record<string, unknown>> : []
  const dynamics = isRecord(report) ? arrayFrom(report, 'dynamics') as Array<Record<string, unknown>> : []
  const context = isRecord(report) && isRecord(report.context) ? report.context : null
  const resultRows = summary && Array.isArray(summary.results) ? summary.results as Array<Record<string, unknown>> : []
  return (
    <>
      <section className="panel report-summary">
        <div className="panel-title">
          <h2>Результат отчёта</h2>
          <span>{isRecord(report) ? `${statusLabel(String(report.status || 'unknown'))} · ${report.experiment_name || short(String(report.experiment_id || ''))}` : ''}</span>
        </div>
        <div className="report-grid">
          <div>
            <span className="caption">Рекомендация</span>
            <strong>{translateReportValue('recommendation', summary && typeof summary.recommendation === 'string' ? summary.recommendation : (isRecord(report) ? report.result : null))}</strong>
          </div>
          <div>
            <span className="caption">Основная метрика</span>
            <strong>{summary && typeof summary.metric_name === 'string' ? summary.metric_name : summary && typeof summary.metric_key === 'string' ? summary.metric_key : '—'}</strong>
          </div>
          <div>
            <span className="caption">Победитель</span>
            <strong>{summary && typeof summary.winner_variant_name === 'string' ? summary.winner_variant_name : 'не выбран'}</strong>
          </div>
          <div>
            <span className="caption">Окно отчёта</span>
            <strong>{context ? `${formatReportValue(context.window_start)} → ${formatReportValue(context.window_end)}` : '—'}</strong>
          </div>
        </div>
        {summaryLines.length > 0 && (
          <ul className="summary-lines">
            {summaryLines.map((line, index) => <li key={index}>{translateSummaryLine(String(line))}</li>)}
          </ul>
        )}
      </section>
      <ReportVariants variants={variants} />
      <DataTable title="Сравнение с контролем" rows={resultRows} columns={['variant_name', 'value', 'vs_control', 'change_percent']} empty="Сводка по основной метрике пока пустая." formatCell={(column, value) => reportCell(column, value)} />
      <DataTable title="Метрики отчёта" rows={metrics} columns={['metric_key', 'name', 'metric_type', 'unit', 'event_expectations']} empty="В отчёте нет блока metrics." formatCell={(column, value) => reportCell(column, value)} />
      <DataTable title="Динамика по дням" rows={dynamics} columns={['date', 'variant_name', 'metric_key', 'value']} empty="Dynamics не вернулся или выключен." formatCell={(column, value) => reportCell(column, value)} />
      <section className="panel">
        <div className="panel-title"><h2>Raw report</h2><span>полный ответ backend для сверки со swagger</span></div>
        <pre className="json-inline">{pretty(report)}</pre>
      </section>
    </>
  )
}

function ReportVariants({ variants }: { variants: Array<Record<string, unknown>> }) {
  if (variants.length === 0) {
    return <section className="panel"><div className="empty-note">Backend вернул отчёт без строк variants.</div></section>
  }
  return (
    <section className="panel">
      <div className="panel-title"><h2>Варианты и метрики</h2><span>{variants.length} вариантов</span></div>
      <div className="variant-report-grid">
        {variants.map((variant, index) => {
          const metricValues = Array.isArray(variant.metric_values) ? variant.metric_values.filter(isRecord) : []
          const eventCounts = isRecord(variant.event_counts) ? Object.entries(variant.event_counts) : []
          return (
            <article className={variant.is_control ? 'variant-report-card control' : 'variant-report-card'} key={String(variant.variant_id || variant.variant_name || index)}>
              <div className="variant-head">
                <div>
                  <h3>{String(variant.variant_name || `Вариант ${index + 1}`)}</h3>
                  <span>{variant.is_control ? 'контрольный вариант' : 'тестовый вариант'}</span>
                </div>
                <code>{short(String(variant.variant_id || ''))}</code>
              </div>
              <div className="variant-kpis">
                <ReportKpi label="Выдач варианта" value={formatReportValue(variant.decisions_count)} />
                <ReportKpi label="Уникальных пользователей" value={formatReportValue(variant.subjects_count)} />
                <ReportKpi label="Доля аудитории" value={formatPercent(variant.share_pct)} />
              </div>
              <div className="mini-section">
                <strong>Метрики</strong>
                {metricValues.length === 0 ? <span className="muted">нет значений</span> : metricValues.map((metric, metricIndex) => (
                  <div className="metric-line" key={`${metric.metric_key || metricIndex}`}>
                    <span>{String(metric.metric_key || 'metric')}</span>
                    <b>{formatReportValue(metric.value)}{metric.unit ? ` ${metric.unit}` : ''}</b>
                  </div>
                ))}
              </div>
              <div className="mini-section">
                <strong>События</strong>
                {eventCounts.length === 0 ? <span className="muted">событий нет</span> : eventCounts.map(([key, value]) => (
                  <div className="metric-line" key={key}>
                    <span>{key}</span>
                    <b>{formatReportValue(value)}</b>
                  </div>
                ))}
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function ReportKpi({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function SafetyModule({ api, catalogs, drafts, updateDraft, refreshAll }: ModuleProps) {
  const d = drafts.guardrail
  return (
    <>
      <ModuleHeader title="Ограничители" description="Правила защитных метрик: порог, окно наблюдения и действие при деградации." />
      <FormCard
        title="Добавить или обновить ограничитель"
        wide
        submitLabel="Сохранить ограничитель"
        onSubmit={async () => {
          await api('POST', '/api/v1/guardrails', { metric_key: d.metric_key, threshold: Number(d.threshold), action: d.action, window_seconds: Number(d.window_seconds) })
          await refreshAll()
        }}
      >
        <div className="form-grid">
          <SelectInput label="Ключ метрики" value={d.metric_key} options={catalogs.metrics.map((m) => String(m.key || '')).filter(Boolean)} onChange={(v) => updateDraft('guardrail', { metric_key: v })} />
          <NumberInput label="Порог" value={d.threshold} onChange={(v) => updateDraft('guardrail', { threshold: v })} />
          <SelectInput label="Действие" value={d.action} options={[{ value: 'pause', label: 'пауза' }, { value: 'rollback_to_control', label: 'откат к контролю' }]} onChange={(v) => updateDraft('guardrail', { action: v })} />
          <NumberInput label="Окно, секунд" value={d.window_seconds} onChange={(v) => updateDraft('guardrail', { window_seconds: v })} />
        </div>
      </FormCard>
      <DataTable title="Правила ограничителей" rows={catalogs.guardrails} columns={['metric_key', 'threshold', 'action', 'window_seconds']} empty="Правил ограничителей нет." />
    </>
  )
}

function LearningsModule({ api, catalogs, drafts, updateDraft, refreshAll }: ModuleProps) {
  const d = drafts.learning
  return (
    <>
      <ModuleHeader title="Библиотека выводов" description="Фиксация вывода эксперимента нужна для завершения, если backend запущен с LEARNINGS_REQUIRED_ON_COMPLETE=true." />
      <FormCard
        title="Заполнить вывод по эксперименту"
        wide
        submitLabel="Сохранить вывод"
        onSubmit={async () => {
          await api('PUT', `/api/v1/experiments/${d.experiment_id}/learning`, clean({
            hypothesis: d.hypothesis,
            notes: d.notes,
            primary_metric_key: d.primary_metric_key,
            result_action: d.result_action,
            result_outcome: d.result_outcome,
            effect_summary: d.effect_summary || null,
            product_tags: splitCsv(d.product_tags),
            countries: [],
            platforms: ['web'],
            app_versions: [],
            variant_structure: {},
            is_completed: true,
          }))
          await refreshAll()
        }}
      >
        <SelectInput label="Эксперимент" value={d.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('learning', { experiment_id: v })} />
        <TextInput label="Гипотеза" value={d.hypothesis} onChange={(v) => updateDraft('learning', { hypothesis: v })} />
        <TextInput label="Заметки" value={d.notes} onChange={(v) => updateDraft('learning', { notes: v })} />
        <div className="form-grid">
          <TextInput label="Основная метрика" value={d.primary_metric_key} onChange={(v) => updateDraft('learning', { primary_metric_key: v })} />
          <SelectInput label="Действие" value={d.result_action} options={['rollout', 'rollback', 'continue', 'repeat']} onChange={(v) => updateDraft('learning', { result_action: v })} />
          <SelectInput label="Итог" value={d.result_outcome} options={['rollout_winner', 'rollback', 'no_effect', 'worse']} onChange={(v) => updateDraft('learning', { result_outcome: v })} />
          <TextInput label="Теги продукта" value={d.product_tags} onChange={(v) => updateDraft('learning', { product_tags: v })} />
        </div>
      </FormCard>
      <DataTable title="Выводы" rows={catalogs.learnings} columns={['experiment_name', 'result_outcome', 'result_action', 'primary_metric_key', 'is_completed', 'id']} empty="Выводов пока нет." />
    </>
  )
}

function ConflictsModule({ api, catalogs, drafts, updateDraft, refreshAll }: ModuleProps) {
  const d = drafts
  return (
    <>
      <ModuleHeader title="Conflict domains" description="Прозрачное разрешение конфликтов между экспериментами в одной продуктовой зоне." />
      <div className="two-col">
        <FormCard
          title="Создать домен"
          submitLabel="Создать домен"
          onSubmit={async () => {
            await api('POST', '/api/v1/conflict-domains', clean(d.conflictDomain))
            await refreshAll()
          }}
        >
          <TextInput label="Key" value={d.conflictDomain.key} onChange={(v) => updateDraft('conflictDomain', { key: v })} />
          <TextInput label="Name" value={d.conflictDomain.name} onChange={(v) => updateDraft('conflictDomain', { name: v })} />
          <SelectInput label="Default policy" value={d.conflictDomain.default_policy} options={['mutual_exclusion', 'bid', 'priority']} onChange={(v) => updateDraft('conflictDomain', { default_policy: v })} />
          <TextInput label="Описание" value={d.conflictDomain.description} onChange={(v) => updateDraft('conflictDomain', { description: v })} />
        </FormCard>
        <FormCard
          title="Привязать эксперимент"
          submitLabel="Привязать"
          onSubmit={async () => {
            await api('POST', `/api/v1/experiments/${d.conflictBinding.experiment_id}/conflict-bindings`, clean({
              domain_id: d.conflictBinding.domain_id,
              policy: d.conflictBinding.policy || null,
              priority_tier: Number(d.conflictBinding.priority_tier),
              bid_value: Number(d.conflictBinding.bid_value),
              is_enabled: d.conflictBinding.is_enabled,
            }))
            await refreshAll()
          }}
        >
          <SelectInput label="Experiment" value={d.conflictBinding.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('conflictBinding', { experiment_id: v })} />
          <SelectInput label="Domain" value={d.conflictBinding.domain_id} options={catalogs.conflictDomains.map((x) => ({ value: String(x.id || ''), label: `${x.key || x.name} (${short(String(x.id || ''))})` }))} onChange={(v) => updateDraft('conflictBinding', { domain_id: v })} />
          <SelectInput label="Policy" value={d.conflictBinding.policy} options={['mutual_exclusion', 'bid', 'priority']} onChange={(v) => updateDraft('conflictBinding', { policy: v })} />
          <NumberInput label="Priority" value={d.conflictBinding.priority_tier} onChange={(v) => updateDraft('conflictBinding', { priority_tier: v })} />
          <Toggle label="Enabled" checked={d.conflictBinding.is_enabled} onChange={(v) => updateDraft('conflictBinding', { is_enabled: v })} />
        </FormCard>
      </div>
      <DataTable title="Conflict domains" rows={catalogs.conflictDomains} columns={['key', 'name', 'default_policy', 'id']} empty="Конфликтных доменов пока нет." />
    </>
  )
}

function RampModule({ api, catalogs, drafts, updateDraft }: ModuleProps) {
  const d = drafts.rampPlan
  const steps = [d.step1, d.step2, d.step3].filter((step) => step > 0).map((traffic_fraction) => ({ traffic_fraction }))
  return (
    <>
      <ModuleHeader title="Автопилот раскатки" description="План ступенчатого увеличения трафика: сколько ждать на каждой ступени, какие минимумы данных нужны и что делать при проблемах." />
      <FormCard
        title="План раскатки"
        wide
        submitLabel="Сохранить план раскатки"
        defaultOpen
        icon={<SlidersHorizontal size={16} />}
        onSubmit={async () => {
          await api('PUT', `/api/v1/experiments/${d.experiment_id}/ramp-plan`, {
            steps,
            observation_window_seconds: Number(d.observation_window_seconds),
            gate_data_sufficiency: {
              min_total_impressions: Number(d.min_total_impressions),
              min_impressions_per_variant: Number(d.min_impressions_per_variant),
              min_minutes_on_step: Number(d.min_minutes_on_step),
            },
            gate_data_health: { require_no_srm: false, require_no_mass_rejected: false },
            gate_safety: {
              use_guardrails: d.use_guardrails,
              error_rate_threshold: Number(d.error_rate_threshold),
              latency_p95_ms: Number(d.latency_p95_ms),
            },
            safety_actions: [{ trigger_type: 'guardrail_triggered', action: d.safety_action }],
          })
        }}
      >
        <div className="helper-strip">
          Окно наблюдения задаётся в секундах: например 3600 = 1 час. Доли трафика указываются от 0 до 1, где 0.1 = 10%, 0.5 = 50%.
        </div>
        <SelectInput label="Эксперимент" value={d.experiment_id} options={catalogs.experiments.map(expOption)} onChange={(v) => updateDraft('rampPlan', { experiment_id: v })} />
        <div className="form-grid">
          <NumberInput label="Ступень 1: доля трафика" value={d.step1} step={0.05} onChange={(v) => updateDraft('rampPlan', { step1: v })} />
          <NumberInput label="Ступень 2: доля трафика" value={d.step2} step={0.05} onChange={(v) => updateDraft('rampPlan', { step2: v })} />
          <NumberInput label="Ступень 3: доля трафика" value={d.step3} step={0.05} onChange={(v) => updateDraft('rampPlan', { step3: v })} />
          <NumberInput label="Окно наблюдения, сек." value={d.observation_window_seconds} onChange={(v) => updateDraft('rampPlan', { observation_window_seconds: v })} />
        </div>
        <div className="field-notes">
          <span><strong>Ступени:</strong> целевая доля аудитории на каждом шаге раскатки.</span>
          <span><strong>Окно:</strong> сколько секунд автопилот ждёт и собирает данные перед оценкой перехода.</span>
        </div>
        <div className="form-grid">
          <NumberInput label="Минимум показов на ступени" value={d.min_total_impressions} onChange={(v) => updateDraft('rampPlan', { min_total_impressions: v })} />
          <NumberInput label="Минимум показов на вариант" value={d.min_impressions_per_variant} onChange={(v) => updateDraft('rampPlan', { min_impressions_per_variant: v })} />
          <NumberInput label="Минимум минут на ступени" value={d.min_minutes_on_step} onChange={(v) => updateDraft('rampPlan', { min_minutes_on_step: v })} />
          <SelectInput label="Действие при срабатывании защиты" value={d.safety_action} options={[{ value: 'pause', label: 'Поставить на паузу' }, { value: 'rollback_to_control', label: 'Откатить к контролю' }, { value: 'step_back', label: 'Вернуться на шаг назад' }]} onChange={(v) => updateDraft('rampPlan', { safety_action: v })} />
        </div>
        <div className="field-notes">
          <span><strong>Минимумы данных:</strong> без них автопилот не должен повышать трафик, даже если всё выглядит хорошо.</span>
          <span><strong>Защитное действие:</strong> что сделать, если guardrail или техническая метрика показывает риск.</span>
        </div>
        <div className="form-grid">
          <Toggle label="Учитывать guardrails" checked={d.use_guardrails} onChange={(v) => updateDraft('rampPlan', { use_guardrails: v })} />
          <NumberInput label="Порог доли ошибок" value={d.error_rate_threshold} step={0.01} onChange={(v) => updateDraft('rampPlan', { error_rate_threshold: v })} />
          <NumberInput label="Порог задержки p95, мс" value={d.latency_p95_ms} onChange={(v) => updateDraft('rampPlan', { latency_p95_ms: v })} />
        </div>
        <div className="field-notes">
          <span><strong>Порог ошибок:</strong> доля от 0 до 1, например 0.01 = 1% ошибок.</span>
          <span><strong>p95 задержки:</strong> максимальная допустимая задержка 95-го перцентиля в миллисекундах.</span>
        </div>
        <div className="button-row">
          <button type="button" className="secondary success" onClick={() => api('POST', `/api/v1/experiments/${d.experiment_id}/ramp-start`)}><Play size={16} />Запустить автопилот</button>
          <button type="button" className="secondary" onClick={() => api('GET', `/api/v1/experiments/${d.experiment_id}/ramp-state`)}><Activity size={16} />Проверить состояние</button>
          <button type="button" className="secondary" onClick={() => api('GET', `/api/v1/experiments/${d.experiment_id}/ramp-decision-log`)}><History size={16} />История решений</button>
        </div>
        <pre className="json-inline compact">{pretty({ steps })}</pre>
      </FormCard>
    </>
  )
}

function RawModule({ api, drafts, updateDraft }: ModuleProps) {
  const d = drafts.raw
  const endpointRows = swaggerEndpoints.map((endpoint) => ({ ...endpoint }))
  return (
    <>
      <ModuleHeader title="Swagger API console" description="Все эндпоинты из Swagger явно перечислены ниже: можно подставить метод, путь и пример body, заменить {id}/{key} на реальные значения и выполнить запрос." />
      <FormCard
        title="HTTP request"
        wide
        defaultOpen
        icon={<TerminalSquare size={16} />}
        tone="neutral"
        submitLabel="Выполнить"
        onSubmit={async () => {
          await api(d.method, d.path, d.method === 'GET' || d.method === 'DELETE' ? undefined : parseJson(d.body))
        }}
      >
        <div className="form-grid">
          <SelectInput label="Method" value={d.method} options={['GET', 'POST', 'PATCH', 'PUT', 'DELETE']} onChange={(v) => updateDraft('raw', { method: v as HttpMethod })} />
          <TextInput label="Path" value={d.path} onChange={(v) => updateDraft('raw', { path: v })} />
        </div>
        <JsonArea label="Body" value={d.body} onChange={(v) => updateDraft('raw', { body: v })} rows={10} />
      </FormCard>
      <section className="panel endpoint-summary">
        <div>
          <span className="caption">Покрытие Swagger</span>
          <strong>{swaggerEndpoints.length} endpoint-ов</strong>
        </div>
        <div>
          <span className="caption">Поддержка</span>
          <strong>метод + путь + пример body</strong>
        </div>
        <div>
          <span className="caption">Как запускать</span>
          <strong>подставьте реальные ID вместо {'{id}'}</strong>
        </div>
      </section>
      <DataTable
        title="Каталог Swagger endpoints"
        rows={endpointRows}
        columns={['tag', 'method', 'path', 'summary']}
        empty="Эндпоинты Swagger не найдены."
        formatCell={(column, value) => column === 'method' ? <span className={`method ${String(value).toLowerCase()}`}>{String(value)}</span> : cell(value)}
        actions={(row) => (
          <button
            className="mini"
            onClick={() => updateDraft('raw', {
              method: row.method as HttpMethod,
              path: String(row.path || ''),
              body: typeof row.body === 'string' ? row.body : '{}',
            })}
          >
            <TerminalSquare size={14} />
            подставить
          </button>
        )}
      />
    </>
  )
}

function Inspector({ log, logs, token, currentUser, onClear }: { log?: RequestLog; logs: RequestLog[]; token: string; currentUser: unknown; onClear: () => void }) {
  const [selectedLogId, setSelectedLogId] = useState('')
  const latestLogId = logs[0]?.id || ''
  const latestSeenLogId = useRef(latestLogId)
  const selectedLog = logs.find((entry) => entry.id === selectedLogId) || log
  useEffect(() => {
    if (selectedLogId && !logs.some((entry) => entry.id === selectedLogId)) setSelectedLogId('')
  }, [logs, selectedLogId])
  useEffect(() => {
    if (!latestLogId) {
      latestSeenLogId.current = ''
      setSelectedLogId('')
      return
    }
    if (latestLogId !== latestSeenLogId.current) {
      latestSeenLogId.current = latestLogId
      setSelectedLogId(latestLogId)
    }
  }, [latestLogId])
  return (
    <aside className="inspector">
      <div className="inspector-head">
        <div>
          <h2>Инспектор API</h2>
          <span>{token ? 'Bearer token сохранён · новые запросы открываются автоматически' : 'Token отсутствует'}</span>
        </div>
        <button className="icon-button" onClick={onClear} title="Очистить историю"><XCircle size={16} /></button>
      </div>
      {currentUser ? <pre className="user-chip">{pretty(currentUser)}</pre> : <div className="empty-note">Выберите аккаунт сверху и войдите. Для полного сценария используйте seed-пользователей из reviewer guide.</div>}
      {selectedLog ? (
        <div className="request-card">
          <div className="request-line">
            <span className={`method ${selectedLog.method.toLowerCase()}`}>{selectedLog.method}</span>
            <strong>{selectedLog.path}</strong>
          </div>
          <div className="response-meta">
            <span className={selectedLog.ok ? 'ok' : 'fail'}>{selectedLog.status}</span>
            <span>{Math.round(selectedLog.duration)} ms</span>
            <span>{selectedLog.at}</span>
          </div>
          <h3>Ответ</h3>
          <pre>{pretty(selectedLog.response)}</pre>
          {selectedLog.request !== undefined && (
            <>
              <h3>Запрос</h3>
              <pre>{pretty(selectedLog.request)}</pre>
            </>
          )}
        </div>
      ) : (
        <div className="empty-note">Здесь появится последний HTTP-запрос.</div>
      )}
      <div className="history-list">
        {logs.slice(0, 12).map((entry) => (
          <button key={entry.id} className={selectedLog?.id === entry.id ? 'history-item active' : 'history-item'} onClick={() => setSelectedLogId(entry.id)} title="Открыть запрос">
            <span className={`method ${entry.method.toLowerCase()}`}>{entry.method}</span>
            <span>{entry.status}</span>
            <p>{entry.path}</p>
          </button>
        ))}
      </div>
    </aside>
  )
}

function ModuleHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="module-header">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </div>
  )
}

function FormCard({
  title,
  children,
  onSubmit,
  submitLabel = 'Выполнить',
  wide = false,
  icon,
  tone = 'primary',
  defaultOpen = false,
}: {
  title: string
  children: ReactNode
  onSubmit: () => void | Promise<void>
  submitLabel?: string
  wide?: boolean
  icon?: ReactNode
  tone?: 'primary' | 'success' | 'warning' | 'danger' | 'neutral'
  defaultOpen?: boolean
}) {
  const [submitting, setSubmitting] = useState(false)
  const [open, setOpen] = useState(defaultOpen)
  return (
    <form
      className={`${wide ? 'form-card wide' : 'form-card'} card ${open ? 'open' : 'collapsed'}`}
      onSubmit={async (event) => {
        event.preventDefault()
        setSubmitting(true)
        try {
          await onSubmit()
        } finally {
          setSubmitting(false)
        }
      }}
    >
      <div className="panel-title">
        <button type="button" className="collapse-trigger" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
          <span className="form-title-icon">{icon || <Plus size={16} />}</span>
          <span>{title}</span>
          <ChevronDown size={16} className="collapse-chevron" />
        </button>
      </div>
      {open && (
        <>
          {children}
          <button className={`primary tone-${tone} btn btn-primary`} disabled={submitting}><Send size={16} />{submitLabel}</button>
        </>
      )}
    </form>
  )
}

function DataTable({ title, rows, columns, empty, actions, formatCell }: { title: string; rows: Array<Record<string, unknown>>; columns: string[]; empty: string; actions?: (row: Record<string, unknown>) => ReactNode; formatCell?: (column: string, value: unknown, row: Record<string, unknown>) => ReactNode }) {
  return (
    <section className="panel table-panel card">
      <div className="panel-title"><h2>{title}</h2><span>{rows.length} строк</span></div>
      {rows.length === 0 ? <div className="empty-note">{empty}</div> : (
        <div className="table-wrap">
          <table className="table table-hover align-middle mb-0">
            <thead>
              <tr>
                {columns.map((col) => <th key={col}>{col}</th>)}
                {actions && <th>действия</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={String(row.id || row.key || index)}>
                  {columns.map((col) => <td key={col}>{formatCell ? formatCell(col, row[col], row) : cell(row[col])}</td>)}
                  {actions && <td>{actions(row)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function GuideCard({ step, title, text }: { step: string; title: string; text: string }) {
  return (
    <section className="guide-card">
      <span>{step}</span>
      <div>
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
    </section>
  )
}

function Stat({ icon, label, value, tone }: { icon: ReactNode; label: string; value: ReactNode; tone?: 'good' | 'warn' | 'bad' }) {
  return (
    <div className={`stat ${tone || ''}`}>
      <div className="stat-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function TextInput({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return <label className="field">{label}<input type={type} value={value} onChange={(event) => onChange(event.target.value)} /></label>
}

function NumberInput({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (value: number) => void; step?: number }) {
  return <label className="field">{label}<input type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>
}

function SelectInput({ label, value, options, onChange }: { label: string; value: string; options: Array<string | { value: string; label: string }>; onChange: (value: string) => void }) {
  return (
    <label className="field">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Не выбрано</option>
        {options.map((option) => {
          const normalized = typeof option === 'string' ? { value: option, label: option } : option
          return <option key={normalized.value} value={normalized.value}>{normalized.label}</option>
        })}
      </select>
    </label>
  )
}

function JsonArea({ label, value, onChange, rows = 5 }: { label: string; value: string; onChange: (value: string) => void; rows?: number }) {
  return <label className="field">{label}<textarea rows={rows} value={value} onChange={(event) => onChange(event.target.value)} /></label>
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="toggle"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>{label}</span></label>
}

function StatusDot({ label, state }: { label: string; state?: 'ok' | 'fail' }) {
  return <span className={`status-dot ${state || ''}`}><span />{label}</span>
}

function useStickyState(key: string, fallback: string) {
  const [value, setValue] = useState(() => localStorage.getItem(key) || fallback)
  useEffect(() => {
    localStorage.setItem(key, value)
  }, [key, value])
  return [value, setValue] as const
}

function parseMaybeJson(text: string) {
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function parseJson(text: string): JsonValue {
  if (!text.trim()) return {}
  return JSON.parse(text) as JsonValue
}

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function arrayFrom(value: unknown, key: string) {
  if (Array.isArray(value)) return value
  if (isRecord(value) && Array.isArray(value[key])) return value[key]
  return []
}

function clean<T extends Record<string, unknown>>(value: T) {
  return Object.fromEntries(Object.entries(value).filter(([, v]) => v !== '' && v !== undefined)) as T
}

function splitCsv(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function hydrateDraftIds(drafts: Drafts, catalogs: Catalogs): Drafts {
  const firstExperiment = catalogs.experiments[0]?.id || ''
  const firstFlag = catalogs.flags[0]?.id || ''
  const firstDomain = String(catalogs.conflictDomains[0]?.id || '')
  return {
    ...drafts,
    experiment: { ...drafts.experiment, flag_id: drafts.experiment.flag_id || firstFlag },
    variant: { ...drafts.variant, experiment_id: drafts.variant.experiment_id || firstExperiment },
    status: { ...drafts.status, experiment_id: drafts.status.experiment_id || firstExperiment },
    report: { ...drafts.report, experiment_id: drafts.report.experiment_id || firstExperiment },
    complete: { ...drafts.complete, experiment_id: drafts.complete.experiment_id || firstExperiment },
    learning: { ...drafts.learning, experiment_id: drafts.learning.experiment_id || firstExperiment },
    conflictBinding: { ...drafts.conflictBinding, experiment_id: drafts.conflictBinding.experiment_id || firstExperiment, domain_id: drafts.conflictBinding.domain_id || firstDomain },
    rampPlan: { ...drafts.rampPlan, experiment_id: drafts.rampPlan.experiment_id || firstExperiment },
  }
}

function expOption(exp: ExperimentItem) {
  return { value: exp.id, label: `${exp.name || exp.id} · ${exp.status || 'unknown'}` }
}

function short(value: string) {
  return value ? value.slice(0, 8) : ''
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: 'черновик',
    on_review: 'на ревью',
    approved: 'одобрен',
    running: 'запущен',
    paused: 'пауза',
    rejected: 'отклонён',
    completed: 'завершён',
    archived: 'архив',
  }
  return labels[status] || status
}

function translateReportValue(column: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  const dictionaries: Record<string, Record<string, string>> = {
    recommendation: {
      rollout: 'раскатить победителя',
      keep_control: 'оставить контроль',
      rollback: 'откатить к контролю',
      no_effect: 'эффект не выявлен',
    },
    metric_type: {
      primary: 'основная',
      auxiliary: 'дополнительная',
      guardrail: 'защитная',
    },
    vs_control: {
      better: 'лучше контроля',
      worse: 'хуже контроля',
      same: 'без изменений',
    },
  }
  const stringValue = String(value)
  return dictionaries[column]?.[stringValue] || stringValue
}

function formatReportValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return Number.isInteger(value) ? value : Number(value.toFixed(4))
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10)
  if (typeof value === 'object') return <code>{JSON.stringify(value)}</code>
  return String(value)
}

function formatPercent(value: unknown): ReactNode {
  if (typeof value !== 'number') return formatReportValue(value)
  return `${Number(value.toFixed(2))}%`
}

function reportCell(column: string, value: unknown) {
  if (column === 'metric_type' || column === 'vs_control') return translateReportValue(column, value)
  if (column === 'change_percent') return value === null || value === undefined ? '—' : `${formatReportValue(value)}%`
  if (column === 'event_expectations') return isRecord(value) ? Object.entries(value).map(([key, direction]) => `${key}: ${direction === 'higher' ? 'рост лучше' : direction === 'lower' ? 'падение лучше' : direction}`).join(', ') : formatReportValue(value)
  return formatReportValue(value)
}

function translateSummaryLine(line: string) {
  return line
    .replace(/\bbecame better\b/gi, 'стал лучше')
    .replace(/\bbecame worse\b/gi, 'стал хуже')
    .replace(/\bbetter\b/gi, 'лучше')
    .replace(/\bworse\b/gi, 'хуже')
    .replace(/\bsame\b/gi, 'без изменений')
    .replace(/\bcontrol\b/gi, 'control')
    .replace(/\btreatment\b/gi, 'treatment')
}

function cell(value: unknown) {
  if (value === null || value === undefined || value === '') return <span className="muted">—</span>
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'object') return <code>{JSON.stringify(value).slice(0, 80)}</code>
  return String(value)
}

function findDecisionId(value: unknown): string {
  if (!isRecord(value)) return ''
  const flags = value.flags
  if (Array.isArray(flags)) {
    for (const item of flags) {
      if (isRecord(item) && typeof item.decision_id === 'string') return item.decision_id
    }
  }
  if (typeof value.decision_id === 'string') return value.decision_id
  return ''
}

function findDecisionAssignment(value: unknown): Record<string, unknown> | null {
  if (!isRecord(value)) return null
  const flags = value.flags
  const candidate = Array.isArray(flags) && flags.find(isRecord)
  const source = isRecord(candidate) ? candidate : value
  const variant = isRecord(source.variant) ? source.variant : null
  const experiment = isRecord(source.experiment) ? source.experiment : null
  return {
    decision_id: source.decision_id,
    flag_key: source.flag_key || source.key,
    value: source.value || source.flag_value || source.variant_value || variant?.variant_value || experiment?.variant,
    variant_name: source.variant_name || variant?.variant_name || variant?.name || experiment?.variant,
    variant_value: source.variant_value || variant?.variant_value || source.flag_value || source.value || experiment?.variant,
    experiment_id: source.experiment_id || experiment?.experiment_id || experiment?.id,
    raw: source,
  }
}

export default App
