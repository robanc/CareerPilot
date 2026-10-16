-- 01_test_reader_role.sql
--
-- Creates the test-only role careerpilot_test_reader. PostgreSQL 16.
--
-- CLUSTER-WIDE EFFECT: roles are global to the PostgreSQL cluster, not to a
-- database. The role becomes visible in every database on this server
-- (including the development database), where it receives only what PUBLIC
-- already has. This script grants it nothing; 02_test_reader_grants.sql
-- grants privileges in careerpilot_test only.
--
-- The role is NOLOGIN: it is used only via SET LOCAL ROLE from a superuser
-- test connection. That tests grants, not containment -- the superuser
-- session can always RESET ROLE. It is NOT the public demo role.
--
-- Idempotent and fail-closed:
-- - Refuses to run unless connected to careerpilot_test as a superuser.
-- - Creates the role only if it is missing.
-- - If it already exists, validates its attributes and memberships and
--   raises on any mismatch. It never ALTERs an existing role.
--
-- Transaction: the script runs its own BEGIN/COMMIT. Any error aborts
-- before COMMIT, so nothing is applied. Do NOT add --single-transaction
-- (it would nest with the BEGIN below).
--
-- Intended invocation (from the repository root; $POSTGRES_USER expands
-- inside the container, so no credential is printed):
--
--   docker compose exec -T db sh -c \
--     'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d careerpilot_test' \
--     < backend/tests/sql/01_test_reader_role.sql

\set ON_ERROR_STOP on

BEGIN;

DO $$
DECLARE
  r pg_roles%ROWTYPE;
BEGIN
  IF current_database() IS DISTINCT FROM 'careerpilot_test' THEN
    RAISE EXCEPTION 'Refusing: connected to %, not careerpilot_test.',
      current_database();
  END IF;

  -- A non-superuser with CREATEROLE would be auto-granted ADMIN membership
  -- in the new role (PostgreSQL 16). Require a superuser so no membership
  -- is created implicitly.
  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
    RAISE EXCEPTION 'Refusing: current_user must be a superuser.';
  END IF;

  SELECT * INTO r FROM pg_roles WHERE rolname = 'careerpilot_test_reader';

  IF NOT FOUND THEN
    CREATE ROLE careerpilot_test_reader
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 0;

    COMMENT ON ROLE careerpilot_test_reader IS
      'Test-only NOLOGIN role: SELECT on careerpilot_test.public tables. '
      'Not the public demo role.';

    SELECT * INTO r FROM pg_roles WHERE rolname = 'careerpilot_test_reader';
  END IF;

  -- Validate (never modify) the role's attributes, whether new or existing.
  IF r.rolcanlogin OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
     OR r.rolinherit OR r.rolreplication OR r.rolbypassrls
     OR r.rolconnlimit IS DISTINCT FROM 0 THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test_reader exists with '
      'unexpected attributes. Review it manually; this script does not '
      'modify existing roles.';
  END IF;

  -- No memberships in either direction: the role must not inherit or SET
  -- into any other role (owner, pg_write_all_data, ...), and no role needs
  -- membership in it (superusers can SET ROLE without one).
  IF EXISTS (SELECT 1 FROM pg_auth_members
             WHERE member = r.oid OR roleid = r.oid) THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test_reader has role '
      'memberships. Review them manually.';
  END IF;
END $$;

COMMIT;
