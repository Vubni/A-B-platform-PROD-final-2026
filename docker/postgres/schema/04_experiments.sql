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

CREATE TABLE IF NOT EXISTS conflict_domains (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR NOT NULL UNIQUE,
    name VARCHAR NOT NULL,
    description TEXT,
    default_policy conflict_policy_type NOT NULL DEFAULT 'mutual_exclusion',
    config_version INTEGER NOT NULL DEFAULT 1 CHECK (config_version >= 1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conflict_domains_key ON conflict_domains(key);

CREATE TABLE IF NOT EXISTS experiment_conflict_bindings (
    experiment_id UUID NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    domain_id UUID NOT NULL REFERENCES conflict_domains(id) ON DELETE CASCADE,
    policy conflict_policy_type,
    priority_tier INTEGER,
    bid_value NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (bid_value >= 0),
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (experiment_id, domain_id)
);

CREATE INDEX IF NOT EXISTS idx_experiment_conflict_bindings_domain
    ON experiment_conflict_bindings(domain_id);
CREATE INDEX IF NOT EXISTS idx_experiment_conflict_bindings_experiment
    ON experiment_conflict_bindings(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_conflict_bindings_enabled
    ON experiment_conflict_bindings(is_enabled);

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
        IF current_setting('app.allow_ramp_apply', true) = '1' THEN
            NULL;
        ELSE
            SELECT audience_fraction INTO af FROM experiments WHERE id = eid;
            SELECT COALESCE(SUM(weight), 0) INTO total_weight FROM experiment_variants WHERE experiment_id = eid;
            IF total_weight IS NULL OR total_weight <> af THEN
                RAISE EXCEPTION 'The sum of variant weights (%s) must match the experiment audience fraction (%s)', total_weight, af;
            END IF;
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
    IF current_setting('app.allow_ramp_apply', true) = '1' THEN
        IF NEW.targeting_rule IS DISTINCT FROM OLD.targeting_rule THEN
            RAISE EXCEPTION 'Ramp apply may only change audience_fraction, not targeting_rule';
        END IF;
        RETURN NEW;
    END IF;
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
    IF current_setting('app.allow_ramp_apply', true) = '1' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
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
