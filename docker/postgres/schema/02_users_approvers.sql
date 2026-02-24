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
