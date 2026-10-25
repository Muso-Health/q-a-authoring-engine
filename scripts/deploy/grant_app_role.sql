-- Stage 3b — create the least-privilege application role and grant it DML only.
--
-- Run as the privileged migrator (qa_migrator) against the target database, AFTER
-- `alembic upgrade head` has created the app's schema and every table (stage 3a) — the grants below
-- need them to exist. The app (Cloud Run) then connects as qa_app through the Cloud SQL Connector.
--
-- Invoke via the proxy runner (it supplies :app_password from Secret Manager, and injects :"db_name"
-- — the database it connected to — for the GRANT CONNECT below; it defaults to `qa_authoring`):
--   scripts/deploy/psql_via_proxy.sh scripts/deploy/grant_app_role.sql \
--       -v app_password="$(gcloud secrets versions access latest --secret=qa-authoring-app-db-password)"
-- For the test environment, pass its database name to the runner:
--   QA_AUTHORING_DB_NAME=qa_authoring_test scripts/deploy/psql_via_proxy.sh scripts/deploy/grant_app_role.sql \
--       -v app_password="$(gcloud secrets versions access latest --secret=qa-authoring-app-db-password)"
--
-- The tables live in the app's own schema (QA_AUTHORING_DB_SCHEMA, `qa_authoring` by default), never
-- in `public`; pass -v schema=<name> if it was changed.

\set ON_ERROR_STOP on

-- The role is cluster-wide (shared by both databases on the instance): LOGIN, but explicitly no
-- superuser / createdb / createrole — DML is all it will hold.
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'qa_app') THEN
      CREATE ROLE qa_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
   END IF;
END
$$;

ALTER ROLE qa_app WITH PASSWORD :'app_password';

-- Which database to GRANT CONNECT on, and which schema holds the tables. The proxy runner injects
-- :"db_name"; both default so nothing breaks when the file is run directly.
\if :{?db_name}
\else
   \set db_name qa_authoring
\endif
\if :{?schema}
\else
   \set schema qa_authoring
\endif

GRANT CONNECT ON DATABASE :"db_name" TO qa_app;
GRANT USAGE ON SCHEMA :"schema" TO qa_app;

-- DML on everything that exists now. Deliberately NO CREATE on the schema (the app never does DDL)
-- and NO TRUNCATE.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA :"schema" TO qa_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA :"schema" TO qa_app;

-- Tables and sequences created by FUTURE migrations (run again as qa_migrator) inherit the same
-- grants automatically, so a later `alembic upgrade` never silently locks the app out.
ALTER DEFAULT PRIVILEGES FOR ROLE qa_migrator IN SCHEMA :"schema"
   GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO qa_app;
ALTER DEFAULT PRIVILEGES FOR ROLE qa_migrator IN SCHEMA :"schema"
   GRANT USAGE, SELECT ON SEQUENCES TO qa_app;

SELECT 'qa_app granted DML on ' || count(*) || ' tables in ' || :'schema' AS result
FROM information_schema.tables
WHERE table_schema = :'schema' AND table_type = 'BASE TABLE';
