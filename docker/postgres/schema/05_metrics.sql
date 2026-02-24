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

CREATE TABLE IF NOT EXISTS metric_guardrails (
    metric_key VARCHAR NOT NULL PRIMARY KEY REFERENCES metric_catalog(key) ON DELETE CASCADE,
    threshold NUMERIC NOT NULL,
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    action VARCHAR NOT NULL CHECK (action IN ('pause', 'rollback_to_control')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
