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
