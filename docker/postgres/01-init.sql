BEGIN;

\i /docker-entrypoint-initdb.d/schema/00_drop.sql
\i /docker-entrypoint-initdb.d/schema/01_types.sql
\i /docker-entrypoint-initdb.d/schema/02_users_approvers.sql
\i /docker-entrypoint-initdb.d/schema/03_feature_flags.sql
\i /docker-entrypoint-initdb.d/schema/04_experiments.sql
\i /docker-entrypoint-initdb.d/schema/05_metrics.sql
\i /docker-entrypoint-initdb.d/schema/06_review_guardrail_snapshots.sql
\i /docker-entrypoint-initdb.d/schema/07_decisions.sql
\i /docker-entrypoint-initdb.d/schema/08_events.sql
\i /docker-entrypoint-initdb.d/schema/09_ramp.sql
\i /docker-entrypoint-initdb.d/schema/10_experiment_attachments.sql

COMMIT;
