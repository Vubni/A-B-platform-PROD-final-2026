CREATE TYPE user_role AS ENUM ('admin', 'experimenter', 'approver', 'viewer');

CREATE TABLE IF NOT EXISTS users (
    id BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY (
        INCREMENT 1 START 1 MINVALUE 1 CACHE 1
    ),
    email VARCHAR UNIQUE NOT NULL,
    first_name VARCHAR UNIQUE NOT NULL,
    password VARCHAR NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    role user_role NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_first_name ON users(first_name);

CREATE TABLE IF NOT EXISTS approver_groups (
    id BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY (
        INCREMENT 1 START 1 MINVALUE 1 CACHE 1
    ),
    experimenter_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    min_approvals INTEGER NOT NULL DEFAULT 1 CHECK (min_approvals >= 1),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id),
    UNIQUE (experimenter_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_approver_groups_fallback_unique
    ON approver_groups ((1)) WHERE experimenter_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_approver_groups_experimenter ON approver_groups(experimenter_id);

CREATE TABLE IF NOT EXISTS approver_group_members (
    approver_group_id BIGINT NOT NULL REFERENCES approver_groups(id) ON DELETE CASCADE,
    approver_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (approver_group_id, approver_id)
);

CREATE INDEX IF NOT EXISTS idx_approver_group_members_group ON approver_group_members(approver_group_id);
CREATE INDEX IF NOT EXISTS idx_approver_group_members_approver ON approver_group_members(approver_id);