CREATE TYPE user_role AS ENUM ('admin', 'experimenter', 'approver', 'viewer');
CREATE TYPE flag_value_type AS ENUM ('string', 'number', 'bool');
CREATE TYPE experiment_status AS ENUM (
    'draft',
    'on_review',
    'approved',
    'running',
    'paused',
    'completed',
    'archived',
    'rejected'
);
CREATE TYPE conflict_policy_type AS ENUM (
    'mutual_exclusion',
    'bid',
    'priority'
);
