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

CREATE TABLE IF NOT EXISTS decision_conflict_log (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id VARCHAR NOT NULL,
    domain_id UUID NOT NULL REFERENCES conflict_domains(id) ON DELETE CASCADE,
    policy_used conflict_policy_type NOT NULL,
    config_version INTEGER NOT NULL,
    winner_experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    losers JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_conflict_log_subject_id
    ON decision_conflict_log(subject_id);
CREATE INDEX IF NOT EXISTS idx_decision_conflict_log_domain_id
    ON decision_conflict_log(domain_id);
CREATE INDEX IF NOT EXISTS idx_decision_conflict_log_created_at
    ON decision_conflict_log(created_at);

CREATE TABLE IF NOT EXISTS subject_experiment_cooldown (
    subject_id VARCHAR NOT NULL PRIMARY KEY,
    entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
