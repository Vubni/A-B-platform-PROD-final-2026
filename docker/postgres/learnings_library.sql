BEGIN;


CREATE TABLE IF NOT EXISTS experiment_learnings (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL UNIQUE REFERENCES experiments(id) ON DELETE CASCADE,
    flag_key VARCHAR NOT NULL,
    owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    owner_team VARCHAR,
    hypothesis TEXT NOT NULL,
    primary_metric_key VARCHAR NOT NULL,
    result_outcome VARCHAR NOT NULL CHECK (
        result_outcome IN ('rollout_winner', 'rollback', 'no_effect', 'worse')
    ),
    result_action VARCHAR NOT NULL CHECK (
        result_action IN ('rollout', 'rollback', 'continue', 'repeat')
    ),
    effect_summary VARCHAR,
    guardrail_triggers_count INTEGER NOT NULL DEFAULT 0 CHECK (guardrail_triggers_count >= 0),
    targeting_summary TEXT,
    platforms TEXT[] NOT NULL DEFAULT '{}',
    countries TEXT[] NOT NULL DEFAULT '{}',
    app_versions TEXT[] NOT NULL DEFAULT '{}',
    product_tags TEXT[] NOT NULL DEFAULT '{}',
    change_type VARCHAR,
    variant_structure JSONB NOT NULL DEFAULT '{}'::jsonb,
    report_url TEXT,
    ticket_url TEXT,
    notes TEXT NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_document TSVECTOR
);

CREATE TABLE IF NOT EXISTS learning_guardrails (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    learning_id UUID NOT NULL REFERENCES experiment_learnings(id) ON DELETE CASCADE,
    metric_key VARCHAR NOT NULL,
    threshold_value NUMERIC,
    trigger_count INTEGER NOT NULL DEFAULT 0 CHECK (trigger_count >= 0),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (learning_id, metric_key)
);

CREATE TABLE IF NOT EXISTS experiment_learning_audit_log (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    learning_id UUID REFERENCES experiment_learnings(id) ON DELETE SET NULL,
    action VARCHAR NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    before_state JSONB,
    after_state JSONB
);

CREATE TABLE IF NOT EXISTS learning_guardrails_audit_log (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    guardrail_id UUID,
    learning_id UUID REFERENCES experiment_learnings(id) ON DELETE SET NULL,
    action VARCHAR NOT NULL CHECK (
        action IN ('guardrail_insert', 'guardrail_update', 'guardrail_delete')
    ),
    changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    before_state JSONB,
    after_state JSONB
);

CREATE TABLE IF NOT EXISTS learning_similarity_cache (
    learning_id UUID NOT NULL REFERENCES experiment_learnings(id) ON DELETE CASCADE,
    similar_learning_id UUID NOT NULL REFERENCES experiment_learnings(id) ON DELETE CASCADE,
    score NUMERIC(6,5) NOT NULL CHECK (score >= 0 AND score <= 1),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    algorithm_version VARCHAR NOT NULL DEFAULT 'v1',
    PRIMARY KEY (learning_id, similar_learning_id),
    CHECK (learning_id <> similar_learning_id)
);

CREATE INDEX IF NOT EXISTS idx_experiment_learnings_flag_key
    ON experiment_learnings(flag_key);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_owner_user
    ON experiment_learnings(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_owner_team
    ON experiment_learnings(owner_team);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_result_outcome
    ON experiment_learnings(result_outcome);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_primary_metric
    ON experiment_learnings(primary_metric_key);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_created_at
    ON experiment_learnings(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_platforms
    ON experiment_learnings USING GIN(platforms);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_countries
    ON experiment_learnings USING GIN(countries);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_tags
    ON experiment_learnings USING GIN(product_tags);
CREATE INDEX IF NOT EXISTS idx_experiment_learnings_search
    ON experiment_learnings USING GIN(search_document);

CREATE INDEX IF NOT EXISTS idx_learning_guardrails_learning
    ON learning_guardrails(learning_id);
CREATE INDEX IF NOT EXISTS idx_learning_guardrails_metric_key
    ON learning_guardrails(metric_key);

CREATE INDEX IF NOT EXISTS idx_experiment_learning_audit_log_learning
    ON experiment_learning_audit_log(learning_id);
CREATE INDEX IF NOT EXISTS idx_experiment_learning_audit_log_changed_at
    ON experiment_learning_audit_log(changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_learning_guardrails_audit_log_learning
    ON learning_guardrails_audit_log(learning_id);
CREATE INDEX IF NOT EXISTS idx_learning_guardrails_audit_log_changed_at
    ON learning_guardrails_audit_log(changed_at DESC);

CREATE INDEX IF NOT EXISTS idx_learning_similarity_cache_source
    ON learning_similarity_cache(learning_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_learning_similarity_cache_target
    ON learning_similarity_cache(similar_learning_id);

CREATE OR REPLACE FUNCTION log_experiment_learning_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO experiment_learning_audit_log (
            learning_id,
            action,
            changed_by,
            before_state,
            after_state
        ) VALUES (
            NEW.id,
            'insert',
            NEW.updated_by,
            NULL,
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO experiment_learning_audit_log (
            learning_id,
            action,
            changed_by,
            before_state,
            after_state
        ) VALUES (
            NEW.id,
            'update',
            NEW.updated_by,
            to_jsonb(OLD),
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO experiment_learning_audit_log (
            learning_id,
            action,
            changed_by,
            before_state,
            after_state
        ) VALUES (
            OLD.id,
            'delete',
            OLD.updated_by,
            to_jsonb(OLD),
            NULL
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_experiment_learning_search_document()
RETURNS TRIGGER AS $$
DECLARE
    exp_name TEXT;
BEGIN
    SELECT e.name INTO exp_name FROM experiments e WHERE e.id = NEW.experiment_id;
    NEW.search_document := to_tsvector(
        'simple',
        coalesce(exp_name, '') || ' ' ||
        coalesce(NEW.flag_key, '') || ' ' ||
        coalesce(NEW.owner_team, '') || ' ' ||
        coalesce(NEW.hypothesis, '') || ' ' ||
        coalesce(NEW.primary_metric_key, '') || ' ' ||
        coalesce(NEW.result_outcome, '') || ' ' ||
        coalesce(NEW.result_action, '') || ' ' ||
        coalesce(NEW.effect_summary, '') || ' ' ||
        coalesce(NEW.change_type, '') || ' ' ||
        coalesce(NEW.targeting_summary, '') || ' ' ||
        coalesce(NEW.notes, '') || ' ' ||
        array_to_string(NEW.product_tags, ' ') || ' ' ||
        array_to_string(NEW.platforms, ' ') || ' ' ||
        array_to_string(NEW.countries, ' ') || ' ' ||
        array_to_string(NEW.app_versions, ' ')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION log_learning_guardrails_changes()
RETURNS TRIGGER AS $$
DECLARE
    actor UUID;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT updated_by INTO actor FROM experiment_learnings WHERE id = NEW.learning_id;
        INSERT INTO learning_guardrails_audit_log (
            guardrail_id,
            learning_id,
            action,
            changed_by,
            before_state,
            after_state
        ) VALUES (
            NEW.id,
            NEW.learning_id,
            'guardrail_insert',
            actor,
            NULL,
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        SELECT updated_by INTO actor FROM experiment_learnings WHERE id = NEW.learning_id;
        INSERT INTO learning_guardrails_audit_log (
            guardrail_id,
            learning_id,
            action,
            changed_by,
            before_state,
            after_state
        ) VALUES (
            NEW.id,
            NEW.learning_id,
            'guardrail_update',
            actor,
            to_jsonb(OLD),
            to_jsonb(NEW)
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        SELECT updated_by INTO actor FROM experiment_learnings WHERE id = OLD.learning_id;
        INSERT INTO learning_guardrails_audit_log (
            guardrail_id,
            learning_id,
            action,
            changed_by,
            before_state,
            after_state
        ) VALUES (
            OLD.id,
            OLD.learning_id,
            'guardrail_delete',
            actor,
            to_jsonb(OLD),
            NULL
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_experiment_learnings_audit ON experiment_learnings;
CREATE TRIGGER tr_experiment_learnings_audit
    AFTER INSERT OR UPDATE OR DELETE ON experiment_learnings
    FOR EACH ROW EXECUTE FUNCTION log_experiment_learning_changes();

DROP TRIGGER IF EXISTS tr_experiment_learnings_search_document ON experiment_learnings;
CREATE TRIGGER tr_experiment_learnings_search_document
    BEFORE INSERT OR UPDATE ON experiment_learnings
    FOR EACH ROW EXECUTE FUNCTION set_experiment_learning_search_document();

DROP TRIGGER IF EXISTS tr_learning_guardrails_audit ON learning_guardrails;
CREATE TRIGGER tr_learning_guardrails_audit
    AFTER INSERT OR UPDATE OR DELETE ON learning_guardrails
    FOR EACH ROW EXECUTE FUNCTION log_learning_guardrails_changes();

COMMIT;
