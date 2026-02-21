BEGIN;

DROP TABLE IF EXISTS events_dependency_queue CASCADE;
DROP TABLE IF EXISTS event_occurrences CASCADE;
DROP TABLE IF EXISTS event_types CASCADE;
DROP TABLE IF EXISTS subject_experiment_cooldown CASCADE;
DROP TABLE IF EXISTS decisions CASCADE;
DROP TABLE IF EXISTS experiment_version_snapshots CASCADE;
DROP TABLE IF EXISTS experiment_ramp_decision_log CASCADE;
DROP TABLE IF EXISTS experiment_ramp_state CASCADE;
DROP TABLE IF EXISTS ramp_safety_actions CASCADE;
DROP TABLE IF EXISTS ramp_steps CASCADE;
DROP TABLE IF EXISTS ramp_plans CASCADE;
DROP TABLE IF EXISTS experiment_guardrail_history CASCADE;
DROP TABLE IF EXISTS experiment_review_history CASCADE;
DROP TABLE IF EXISTS experiment_metrics CASCADE;
DROP TABLE IF EXISTS experiment_variants CASCADE;
DROP TABLE IF EXISTS experiments CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS approver_group_members CASCADE;
DROP TABLE IF EXISTS approver_groups CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS metric_catalog CASCADE;
DROP FUNCTION IF EXISTS check_experiment_variants_invariants() CASCADE;
DROP FUNCTION IF EXISTS check_experiment_audience_fraction() CASCADE;
DROP FUNCTION IF EXISTS check_experiment_frozen_params() CASCADE;
DROP FUNCTION IF EXISTS check_experiment_variants_frozen() CASCADE;
DROP TYPE IF EXISTS experiment_status CASCADE;
DROP TYPE IF EXISTS flag_value_type CASCADE;
DROP TYPE IF EXISTS user_role CASCADE;

CREATE TYPE user_role AS ENUM ('admin', 'experimenter', 'approver', 'viewer');

CREATE TABLE IF NOT EXISTS users (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR UNIQUE NOT NULL,
    first_name VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    role user_role NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_first_name ON users(first_name);

CREATE TABLE IF NOT EXISTS approver_groups (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experimenter_id UUID REFERENCES users(id) ON DELETE CASCADE,
    min_approvals INTEGER NOT NULL DEFAULT 1 CHECK (min_approvals >= 1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (experimenter_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_approver_groups_fallback_unique
    ON approver_groups ((1)) WHERE experimenter_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_approver_groups_experimenter ON approver_groups(experimenter_id);

CREATE TABLE IF NOT EXISTS approver_group_members (
    approver_group_id UUID NOT NULL REFERENCES approver_groups(id) ON DELETE CASCADE,
    approver_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (approver_group_id, approver_id)
);

CREATE INDEX IF NOT EXISTS idx_approver_group_members_group ON approver_group_members(approver_group_id);
CREATE INDEX IF NOT EXISTS idx_approver_group_members_approver ON approver_group_members(approver_id);

CREATE TYPE flag_value_type AS ENUM ('string', 'number', 'bool');

CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR NOT NULL UNIQUE,
    value_type flag_value_type NOT NULL,
    default_value TEXT NOT NULL,
    description VARCHAR,
    owner VARCHAR,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_feature_flags_key ON feature_flags(key);
CREATE INDEX IF NOT EXISTS idx_feature_flags_owner ON feature_flags(owner);


CREATE TYPE experiment_status AS ENUM (
    'draft',
    'on_review',
    'approved',
    'running',
    'paused',
    'completed',
    'archived',
    'rejected'
);

CREATE TABLE IF NOT EXISTS experiments (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    flag_id UUID NOT NULL REFERENCES feature_flags(id) ON DELETE RESTRICT,
    name VARCHAR NOT NULL,
    status experiment_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    audience_fraction NUMERIC(5,4) NOT NULL CHECK (audience_fraction > 0 AND audience_fraction <= 1),
    targeting_rule TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiments_flag ON experiments(flag_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_created_by ON experiments(created_by);

CREATE UNIQUE INDEX IF NOT EXISTS idx_experiments_one_active_per_flag
    ON experiments(flag_id) WHERE status IN ('running', 'paused');

CREATE TABLE IF NOT EXISTS experiment_variants (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    variant_name VARCHAR NOT NULL,
    variant_value TEXT NOT NULL,
    weight NUMERIC(5,4) NOT NULL CHECK (weight >= 0),
    is_control BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (experiment_id, variant_name)
);

CREATE INDEX IF NOT EXISTS idx_experiment_variants_experiment ON experiment_variants(experiment_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_variants_one_control
    ON experiment_variants(experiment_id) WHERE is_control = TRUE;

ALTER TABLE experiments ADD COLUMN IF NOT EXISTS completion_outcome VARCHAR
    CHECK (completion_outcome IS NULL OR completion_outcome IN ('rollout_winner', 'rollback', 'no_effect'));
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS completion_comment TEXT;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS completion_winner_variant_id UUID REFERENCES experiment_variants(id) ON DELETE SET NULL;

CREATE OR REPLACE FUNCTION check_experiment_variants_invariants()
RETURNS TRIGGER AS $$
DECLARE
    eid UUID;
    af NUMERIC;
    total_weight NUMERIC;
    control_count INT;
    variant_count INT;
BEGIN
    eid := COALESCE(NEW.experiment_id, OLD.experiment_id);
    SELECT COUNT(*) INTO variant_count FROM experiment_variants WHERE experiment_id = eid;
    IF variant_count = 0 THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    SELECT COUNT(*) INTO control_count FROM experiment_variants WHERE experiment_id = eid AND is_control = TRUE;
    IF control_count <> 1 THEN
        RAISE EXCEPTION 'Experiment must have exactly one control variant (is_control = true). Currently: %', control_count;
    END IF;
    IF variant_count >= 2 THEN
        SELECT audience_fraction INTO af FROM experiments WHERE id = eid;
        SELECT COALESCE(SUM(weight), 0) INTO total_weight FROM experiment_variants WHERE experiment_id = eid;
        IF total_weight IS NULL OR total_weight <> af THEN
            RAISE EXCEPTION 'The sum of variant weights (%s) must match the experiment audience fraction (%s)', total_weight, af;
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_experiment_variants
    AFTER INSERT OR UPDATE OR DELETE ON experiment_variants
    FOR EACH ROW EXECUTE FUNCTION check_experiment_variants_invariants();

CREATE OR REPLACE FUNCTION check_experiment_audience_fraction()
RETURNS TRIGGER AS $$
DECLARE
    total_weight NUMERIC;
BEGIN
    IF NEW.audience_fraction IS NOT DISTINCT FROM OLD.audience_fraction THEN
        RETURN NEW;
    END IF;
    SELECT COALESCE(SUM(weight), 0) INTO total_weight FROM experiment_variants WHERE experiment_id = NEW.id;
    IF (SELECT COUNT(*) FROM experiment_variants WHERE experiment_id = NEW.id) > 0 AND total_weight <> NEW.audience_fraction THEN
        RAISE EXCEPTION 'Сумма весов вариантов (%) должна совпадать с долей аудитории (%)', total_weight, NEW.audience_fraction;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_experiment_audience_fraction
    AFTER UPDATE OF audience_fraction ON experiments
    FOR EACH ROW EXECUTE FUNCTION check_experiment_audience_fraction();

CREATE OR REPLACE FUNCTION check_experiment_frozen_params()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('running', 'paused') AND (
        NEW.audience_fraction IS DISTINCT FROM OLD.audience_fraction
        OR NEW.targeting_rule IS DISTINCT FROM OLD.targeting_rule
    ) THEN
        RAISE EXCEPTION 'Cannot change audience fraction or targeting rule for experiment in status %', OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_experiment_frozen_params
    AFTER UPDATE ON experiments
    FOR EACH ROW EXECUTE FUNCTION check_experiment_frozen_params();

CREATE OR REPLACE FUNCTION check_experiment_variants_frozen()
RETURNS TRIGGER AS $$
DECLARE
    s experiment_status;
BEGIN
    s := (SELECT status FROM experiments WHERE id = COALESCE(NEW.experiment_id, OLD.experiment_id));
    IF s IN ('running', 'paused') THEN
        RAISE EXCEPTION 'Cannot change experiment variants in status %', s;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_check_experiment_variants_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON experiment_variants
    FOR EACH ROW EXECUTE FUNCTION check_experiment_variants_frozen();

CREATE TABLE IF NOT EXISTS experiment_metrics (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    metric_key VARCHAR NOT NULL,
    metric_type VARCHAR NOT NULL CHECK (metric_type IN ('primary', 'auxiliary', 'guardrail')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (experiment_id, metric_key, metric_type)
);

CREATE INDEX IF NOT EXISTS idx_experiment_metrics_experiment ON experiment_metrics(experiment_id);

CREATE TABLE IF NOT EXISTS metric_catalog (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    description TEXT,
    aggregation_rule JSONB NOT NULL,
    attribution_rule JSONB,
    event_expectations JSONB,
    unit VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_metric_catalog_key ON metric_catalog(key);

ALTER TABLE metric_catalog ADD COLUMN IF NOT EXISTS attribution_rule JSONB;
ALTER TABLE metric_catalog ADD COLUMN IF NOT EXISTS event_expectations JSONB;

CREATE TABLE IF NOT EXISTS experiment_review_history (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    reviewer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR NOT NULL CHECK (action IN ('approved', 'requested_changes', 'rejected')),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiment_review_history_experiment ON experiment_review_history(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_review_history_reviewer ON experiment_review_history(reviewer_id);

CREATE TABLE IF NOT EXISTS metric_guardrails (
    metric_key VARCHAR NOT NULL PRIMARY KEY REFERENCES metric_catalog(key) ON DELETE CASCADE,
    threshold NUMERIC NOT NULL,
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    action VARCHAR NOT NULL CHECK (action IN ('pause', 'rollback_to_control')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS experiment_guardrail_history (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    metric_key VARCHAR NOT NULL,
    threshold NUMERIC,
    window_seconds INTEGER,
    action VARCHAR CHECK (action IN ('pause', 'rollback_to_control')),
    metric_value NUMERIC,
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_experiment_guardrail_history_experiment ON experiment_guardrail_history(experiment_id);

CREATE TABLE IF NOT EXISTS experiment_version_snapshots (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiment_version_snapshots_experiment ON experiment_version_snapshots(experiment_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_experiment_version_snapshots_version
    ON experiment_version_snapshots(experiment_id, version);

CREATE TABLE IF NOT EXISTS decisions (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL UNIQUE,
    subject_id VARCHAR NOT NULL,
    flag_id UUID NOT NULL REFERENCES feature_flags(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    experiment_id UUID REFERENCES experiments(id) ON DELETE SET NULL,
    variant_id UUID REFERENCES experiment_variants(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_decisions_decision_id ON decisions(decision_id);
CREATE INDEX IF NOT EXISTS idx_decisions_subject_id ON decisions(subject_id);
CREATE INDEX IF NOT EXISTS idx_decisions_flag_id ON decisions(flag_id);
CREATE INDEX IF NOT EXISTS idx_decisions_experiment_id ON decisions(experiment_id);
CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at);

CREATE TABLE IF NOT EXISTS subject_experiment_cooldown (
    subject_id VARCHAR NOT NULL PRIMARY KEY,
    entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_types (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR NOT NULL UNIQUE,
    display_name VARCHAR,
    description TEXT,
    required_params JSONB,
    validation_type VARCHAR(64),
    report_alert_config JSONB,
    status VARCHAR NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    is_critical BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_event_types_key ON event_types(key);
CREATE INDEX IF NOT EXISTS idx_event_types_status ON event_types(status);

ALTER TABLE event_types ADD COLUMN IF NOT EXISTS requires_show_event_type_id UUID REFERENCES event_types(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_event_types_requires_show ON event_types(requires_show_event_type_id);

CREATE TABLE IF NOT EXISTS event_occurrences (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id VARCHAR NOT NULL UNIQUE,
    decision_id UUID NOT NULL REFERENCES decisions(decision_id) ON DELETE RESTRICT,
    event_type_id UUID NOT NULL REFERENCES event_types(id) ON DELETE RESTRICT,
    subject_id VARCHAR NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_event_occurrences_event_id ON event_occurrences(event_id);
CREATE INDEX IF NOT EXISTS idx_event_occurrences_decision_id ON event_occurrences(decision_id);
CREATE INDEX IF NOT EXISTS idx_event_occurrences_event_type_id ON event_occurrences(event_type_id);
CREATE INDEX IF NOT EXISTS idx_event_occurrences_subject_id ON event_occurrences(subject_id);
CREATE INDEX IF NOT EXISTS idx_event_occurrences_timestamp ON event_occurrences("timestamp");

-- Очередь ожидающих событий (show → conversion): хранение до EVENTS_DEPENDENCY_MAX_DELAY_DAYS дней
CREATE TABLE IF NOT EXISTS events_dependency_queue (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id UUID NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    required_show_event_type_id UUID NOT NULL REFERENCES event_types(id) ON DELETE CASCADE,
    event_id VARCHAR NOT NULL,
    event_type_id UUID NOT NULL REFERENCES event_types(id) ON DELETE CASCADE,
    subject_id VARCHAR NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL,
    payload JSONB,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_dependency_queue_pop
    ON events_dependency_queue(decision_id, required_show_event_type_id);
CREATE INDEX IF NOT EXISTS idx_events_dependency_queue_queued_at
    ON events_dependency_queue(queued_at);

-- =============================================================================
-- Autopilot Ramp-up: умная раскатка по ступеням трафика с gates и safety
-- =============================================================================

CREATE TABLE IF NOT EXISTS ramp_plans (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL UNIQUE REFERENCES experiments(id) ON DELETE CASCADE,
    observation_window_seconds INTEGER NOT NULL CHECK (observation_window_seconds > 0),
    gate_data_sufficiency JSONB NOT NULL DEFAULT '{}',
    gate_safety JSONB NOT NULL DEFAULT '{}',
    gate_data_health JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ramp_plans_experiment ON ramp_plans(experiment_id);

CREATE TABLE IF NOT EXISTS ramp_steps (
    ramp_plan_id UUID NOT NULL REFERENCES ramp_plans(id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL CHECK (step_index >= 0),
    traffic_fraction NUMERIC(5,4) NOT NULL CHECK (traffic_fraction > 0 AND traffic_fraction <= 1),
    PRIMARY KEY (ramp_plan_id, step_index)
);

CREATE INDEX IF NOT EXISTS idx_ramp_steps_plan ON ramp_steps(ramp_plan_id);

CREATE TABLE IF NOT EXISTS ramp_safety_actions (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    ramp_plan_id UUID NOT NULL REFERENCES ramp_plans(id) ON DELETE CASCADE,
    trigger_type VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL CHECK (action IN ('pause', 'rollback_to_control', 'step_back')),
    notify BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_ramp_safety_actions_plan ON ramp_safety_actions(ramp_plan_id);

CREATE TABLE IF NOT EXISTS experiment_ramp_state (
    experiment_id UUID NOT NULL PRIMARY KEY REFERENCES experiments(id) ON DELETE CASCADE,
    ramp_plan_id UUID NOT NULL REFERENCES ramp_plans(id) ON DELETE CASCADE,
    current_step_index INTEGER NOT NULL CHECK (current_step_index >= 0),
    mode VARCHAR(32) NOT NULL DEFAULT 'autopilot' CHECK (mode IN ('autopilot', 'manual', 'paused')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_eval_at TIMESTAMPTZ,
    manual_override_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    manual_override_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS experiment_ramp_decision_log (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action VARCHAR(64) NOT NULL,
    from_step_index INTEGER,
    to_step_index INTEGER,
    reason JSONB,
    triggered_by VARCHAR(32) NOT NULL CHECK (triggered_by IN ('autopilot', 'manual')),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiment_ramp_decision_log_experiment ON experiment_ramp_decision_log(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_ramp_decision_log_decided_at ON experiment_ramp_decision_log(decided_at);

COMMIT;