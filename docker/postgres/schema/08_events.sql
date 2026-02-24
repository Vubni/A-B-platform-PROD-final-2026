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
