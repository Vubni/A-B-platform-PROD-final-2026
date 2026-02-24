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
    step_entered_at TIMESTAMPTZ,
    last_eval_at TIMESTAMPTZ,
    manual_override_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    manual_override_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE experiment_ramp_state ADD COLUMN IF NOT EXISTS step_entered_at TIMESTAMPTZ;
UPDATE experiment_ramp_state SET step_entered_at = started_at WHERE step_entered_at IS NULL;

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
