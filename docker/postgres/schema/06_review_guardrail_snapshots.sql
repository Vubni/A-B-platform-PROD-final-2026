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
