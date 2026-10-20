-- 02_test_reader_grants.sql
--
-- Grants careerpilot_test_reader SELECT-only access in careerpilot_test.
-- PostgreSQL 16. Run after 01_test_reader_role.sql.
--
-- SCOPE: every change below is confined to careerpilot_test:
-- - REVOKE TEMPORARY names careerpilot_test explicitly. The ACL lives in the
--   shared catalog pg_database, but only this database's entry changes.
-- - Schema/table grants and default privileges are stored in this
--   database's catalogs only.
-- No other database is altered.
--
-- Effects:
-- - PUBLIC loses TEMPORARY on careerpilot_test (it keeps CONNECT). PUBLIC is
--   how the reader would get TEMP, so it cannot be revoked from the reader
--   alone. The owner keeps TEMP explicitly; superusers bypass the check.
-- - Reader: USAGE on schema public, SELECT on existing public tables, and
--   SELECT on tables current_user creates in public later (the test
--   fixture's drop_all/create_all recreates them before every test).
-- - Nothing else: no sequence, function, CREATE, or TEMP privileges.
--
-- Fail-closed checks run before any change (connected database, superuser,
-- role attributes, ownership) and after (resulting privileges). Any failure
-- aborts the transaction, so nothing is applied.
--
-- Idempotent: re-running GRANT/REVOKE/ALTER DEFAULT PRIVILEGES is a no-op.
--
-- Run as the SAME role pytest connects as (POSTGRES_USER): default
-- privileges apply only to tables created by the role running this script.
-- The checks below verify that this role owns the database and every
-- existing relation in public.
--
-- Transaction: the script runs its own BEGIN/COMMIT. Do NOT add
-- --single-transaction (it would nest with the BEGIN below).
--
-- Intended invocation (from the repository root; $POSTGRES_USER expands
-- inside the container, so no credential is printed):
--
--   docker compose exec -T db sh -c \
--     'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d careerpilot_test' \
--     < backend/tests/sql/02_test_reader_grants.sql

\set ON_ERROR_STOP on

BEGIN;

-- Pre-checks ---------------------------------------------------------------

DO $$
DECLARE
  r pg_roles%ROWTYPE;
  unexpected text;
BEGIN
  IF current_database() IS DISTINCT FROM 'careerpilot_test' THEN
    RAISE EXCEPTION 'Refusing: connected to %, not careerpilot_test.',
      current_database();
  END IF;

  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
    RAISE EXCEPTION 'Refusing: current_user must be a superuser.';
  END IF;

  -- The role must exist with exactly the attributes 01 creates.
  SELECT * INTO r FROM pg_roles WHERE rolname = 'careerpilot_test_reader';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test_reader does not exist. '
      'Run 01_test_reader_role.sql first.';
  END IF;
  IF r.rolcanlogin OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
     OR r.rolinherit OR r.rolreplication OR r.rolbypassrls
     OR r.rolconnlimit IS DISTINCT FROM 0 THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test_reader has unexpected '
      'attributes.';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_auth_members
             WHERE member = r.oid OR roleid = r.oid) THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test_reader has role '
      'memberships.';
  END IF;

  -- The reader must own nothing, in any database. pg_shdepend is a shared
  -- catalog, so this covers the whole cluster. (Owning a database would
  -- also make it a member of pg_database_owner, which owns schema public.)
  IF EXISTS (SELECT 1 FROM pg_shdepend
             WHERE refclassid = 'pg_authid'::regclass
               AND refobjid = r.oid AND deptype = 'o') THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test_reader owns objects.';
  END IF;

  -- The table creator assumption: current_user owns this database and every
  -- existing relation in public (job_applications and its sequence).
  IF NOT EXISTS (SELECT 1 FROM pg_database
                 WHERE datname = 'careerpilot_test'
                   AND datdba = current_user::regrole) THEN
    RAISE EXCEPTION 'Refusing: careerpilot_test is not owned by current_user.';
  END IF;

  IF (SELECT nspowner FROM pg_namespace WHERE nspname = 'public')
     IS DISTINCT FROM 'pg_database_owner'::regrole THEN
    RAISE EXCEPTION 'Refusing: schema public is not owned by '
      'pg_database_owner.';
  END IF;

  SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO unexpected
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public'
     AND c.relowner <> current_user::regrole;
  IF unexpected IS NOT NULL THEN
    RAISE EXCEPTION 'Refusing: relations in public not owned by '
      'current_user: %.', unexpected;
  END IF;
END $$;

-- Changes ------------------------------------------------------------------

-- PUBLIC hardening, this database only.
REVOKE TEMPORARY ON DATABASE careerpilot_test FROM PUBLIC;

-- Explicit USAGE, so access does not depend on PUBLIC's schema grant.
GRANT USAGE ON SCHEMA public TO careerpilot_test_reader;

-- Existing tables (and any views); sequences are not included.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO careerpilot_test_reader;

-- Future tables created by current_user (no FOR ROLE = current_user) in
-- public. Survives the fixture's drop_all/create_all.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO careerpilot_test_reader;

-- Post-checks: verify the resulting privileges before COMMIT ------------------

DO $$
DECLARE
  reader CONSTANT name := 'careerpilot_test_reader';
  reader_oid CONSTANT oid := to_regrole('careerpilot_test_reader');
  bad text;
  seq record;
  db_oid oid := (SELECT oid FROM pg_database
                 WHERE datname = 'careerpilot_test');
BEGIN
  IF has_database_privilege(reader, 'careerpilot_test', 'TEMPORARY') THEN
    RAISE EXCEPTION 'Post-check failed: reader still has TEMPORARY.';
  END IF;
  IF has_database_privilege(reader, 'careerpilot_test', 'CREATE') THEN
    RAISE EXCEPTION 'Post-check failed: reader has CREATE on the database.';
  END IF;

  IF NOT has_schema_privilege(reader, 'public', 'USAGE') THEN
    RAISE EXCEPTION 'Post-check failed: reader lacks USAGE on public.';
  END IF;
  IF has_schema_privilege(reader, 'public', 'CREATE') THEN
    RAISE EXCEPTION 'Post-check failed: reader has CREATE on public.';
  END IF;

  IF pg_has_role(reader, 'pg_write_all_data', 'MEMBER')
     OR pg_has_role(reader, 'pg_read_all_data', 'MEMBER') THEN
    RAISE EXCEPTION 'Post-check failed: reader has a predefined data role.';
  END IF;

  -- Tables: SELECT only, without grant option. (Column-level grants are not
  -- visible to has_table_privilege; the pg_shdepend check below rejects them.)
  SELECT string_agg(c.relname, ', ' ORDER BY c.relname) INTO bad
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
     AND (NOT has_table_privilege(reader, c.oid, 'SELECT')
          OR has_table_privilege(reader, c.oid,
               'SELECT WITH GRANT OPTION, INSERT, UPDATE, DELETE, TRUNCATE, '
               'REFERENCES, TRIGGER'));
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'Post-check failed: tables not SELECT-only: %.', bad;
  END IF;

  -- Sequences: no access at all (no nextval/setval/currval).
  -- has_sequence_privilege raises an error for a non-sequence, and SQL does
  -- not guarantee that WHERE conditions are evaluated in the order written
  -- (the planner may apply them in any order, before or after the join).
  -- The loop calls it only for rows already selected as sequences.
  bad := NULL;
  FOR seq IN SELECT c.oid, c.relname
               FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public' AND c.relkind = 'S'
              ORDER BY c.relname
  LOOP
    -- IS NOT FALSE: a NULL result (sequence gone) also fails closed.
    IF has_sequence_privilege(reader, seq.oid, 'USAGE, SELECT, UPDATE')
       IS NOT FALSE THEN
      bad := concat_ws(', ', bad, seq.relname);
    END IF;
  END LOOP;
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'Post-check failed: reader can use sequences: %.', bad;
  END IF;

  -- Default privileges: exactly SELECT for the reader on future tables
  -- created by current_user in public.
  IF (SELECT array_agg(a.privilege_type ORDER BY a.privilege_type)
        FROM pg_default_acl d, aclexplode(d.defaclacl) a
       WHERE d.defaclrole = current_user::regrole
         AND d.defaclnamespace = 'public'::regnamespace
         AND d.defaclobjtype = 'r'
         AND a.grantee = reader_oid)
     IS DISTINCT FROM ARRAY['SELECT']::text[] THEN
    RAISE EXCEPTION 'Post-check failed: default privileges for the reader '
      'are not exactly SELECT on tables.';
  END IF;

  -- No other default privileges for the reader in this database (other
  -- creators, schemas, global defaults, sequences/functions/types/schemas),
  -- and no grant option.
  IF EXISTS (SELECT 1
               FROM pg_default_acl d, aclexplode(d.defaclacl) a
              WHERE a.grantee = reader_oid
                AND (a.is_grantable
                     OR d.defaclrole <> current_user::regrole
                     OR d.defaclnamespace <> 'public'::regnamespace
                     OR d.defaclobjtype <> 'r')) THEN
    RAISE EXCEPTION 'Post-check failed: unexpected default privileges for '
      'the reader.';
  END IF;

  -- Every shared-dependency reference to the reader must be an ACL entry
  -- created above in this database. pg_shdepend is a shared catalog; in
  -- PostgreSQL 16 it records owner ('o'), ACL ('a'), and RLS policy ('r')
  -- references to a role, in any database. dbid 0 marks shared objects
  -- (database, tablespace, and parameter ACLs), which 01 and this script
  -- never grant, so dbid 0 is rejected too. Role comments live in
  -- pg_shdescription and never appear here. Column-level ACLs appear as
  -- pg_class rows with objsubid <> 0 and are rejected.
  --
  -- LIMIT: this proves only that no role-specific references exist outside
  -- this database. It cannot see PUBLIC grants (e.g. CONNECT and TEMPORARY
  -- on other databases, EXECUTE on functions), which the reader receives in
  -- every database. Cross-database privilege isolation therefore needs a
  -- separate per-database verification; the reader being NOLOGIN with no
  -- memberships is what keeps it out of other databases today.
  SELECT string_agg(format('dbid=%s %s/%s/%s %s', s.dbid,
                           s.classid::regclass, s.objid, s.objsubid,
                           s.deptype), ', ') INTO bad
    FROM pg_shdepend s
   WHERE s.refclassid = 'pg_authid'::regclass
     AND s.refobjid = reader_oid
     AND NOT (s.dbid = db_oid AND s.deptype = 'a' AND (
              (s.classid = 'pg_namespace'::regclass
               AND s.objid = 'public'::regnamespace
               AND s.objsubid = 0)
           OR (s.classid = 'pg_class'::regclass
               AND s.objsubid = 0
               AND s.objid IN (SELECT c.oid FROM pg_class c
                                WHERE c.relnamespace = 'public'::regnamespace
                                  AND c.relkind IN ('r', 'p')))
           OR (s.classid = 'pg_default_acl'::regclass
               AND s.objid IN (SELECT d.oid FROM pg_default_acl d
                                WHERE d.defaclrole = current_user::regrole
                                  AND d.defaclnamespace = 'public'::regnamespace
                                  AND d.defaclobjtype = 'r'))));
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'Post-check failed: unexpected references to the '
      'reader: %.', bad;
  END IF;
END $$;

COMMIT;
