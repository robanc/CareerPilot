# Deploying the CareerPilot public demo to Render

Status: **ON HOLD — prepared, not deployed. `public_demo` is NOT SAFE TO DEPLOY**
until every step below has been approved, completed, and verified. The
procedure below has not been completed; see "Current status".

## Current status (ON HOLD)

Public deployment is **on hold**. An external connection to the Render
PostgreSQL database failed during authentication with:

    FATAL: SCRAM channel binding check failed

- **Root cause:** unconfirmed.
- **Render Support:** a support request has been submitted; confirmation is
  pending.
- **Tracking:** [GitHub Issue #3](https://github.com/robanc/CareerPilot/issues/3),
  which is open. The
  [Claude Code review of Issue #3](https://github.com/robanc/CareerPilot/issues/3#issuecomment-6406935494)
  compares this preparation with the issue's acceptance criteria.

No further database provisioning or deployment step is to be performed
until Render Support confirms that authentication and the role work.

State of each procedure step. "Reported" means recorded in the project
documentation, not independently verified in this guide.

| Step | State |
|---|---|
| 1. Merge to `main` | The Blueprint (`render.yaml`) and this guide are on `main`. |
| 2. Create Render resources | Reported as provisioned (`README.md`, Deployment). The API host in `render.yaml` is consistent with that. Not independently verified here. |
| 3. Read-only capability check | **Blocked.** The external connection failed at authentication, so the capability query has not returned results. Superuser, CREATEROLE, database owner, and TLS remain unverified. |
| 4. Stage the SQL | Not executed. |
| 5. Schema and SELECT-only role | Not executed. Schema provisioning and SELECT-only role verification are pending. |
| 6. Reader password | Not executed. |
| 7. Fictional seed data | Not executed. |
| 8. Close the database | Pending. If a `/32` was added to the allowlist for the failed connection attempt, confirm it has been removed. |
| 9. API and release workflow configuration | Not completed or verified. This includes `CAREERPILOT_DEMO_DATABASE_URL`, the GitHub `production` environment approval configuration, the deploy hook secrets, and the URL variables. |
| 10. Release and smoke tests | Not executed. No successful deployment, no public smoke test, and no working public URL. |

## Architecture

    Browser -> careerpilot-web (Render static site, frontend/dist)
                 /api/* rewrite -> careerpilot-api (Docker, CAREERPILOT_MODE=public_demo)
                                     -> careerpilot-db (Render Postgres 16)
                                        as careerpilot_demo_reader (SELECT-only)

- `render.yaml` defines all three resources. It contains no secrets, and
  **no service auto-deploys** (`autoDeployTrigger: "off"`).
- Releases go only through `.github/workflows/deploy.yml`, which you start by
  hand. It runs from `main` only, needs the typed confirmation `DEPLOY`, runs
  the full CI suite on that commit, and pauses for approval in the
  `production` environment. Then it calls the Render deploy hooks at that
  commit and runs `ops/smoke-test-render.sh`.
- The API never sees owner credentials:
  - `CAREERPILOT_DEMO_DATABASE_URL` is entered by hand and uses the reader
    role.
  - Startup refuses `DATABASE_URL` or `CAREERPILOT_ADMIN_DATABASE_URL`.
  - Startup refuses a role with any write privilege
    (`verify_demo_role_privileges`).
- The owner credentials are used only from your machine: to create the
  schema and the role (`deploy/render/*.sql.review`) and to seed fictional
  data (`backend/scripts/seed_demo_data.py`).

## What we know about Render (researched 2026-10-20)

| Question | Finding | Status |
|---|---|---|
| Can the default database user create a SELECT-only role? | Render's credentials page says users "created directly with the CREATE USER command are not managed by Render", which implies the default user may run `CREATE USER`. Render does not document the user's attributes. | **Unverified.** Step 2 checks it read-only before anything else. |
| Is the default user a superuser? | Not documented; managed providers normally do not grant it. The provisioning SQL *requires* a non-superuser (that also rules out local Docker clusters). | Unverified (step 2) |
| Do users added in the dashboard help? | Each added credential becomes the new *default* user with full owner access, so it is not a read-only option. | Documented |
| Blueprint fields used | `autoDeployTrigger: off`, `sync: false`, `postgresMajorVersion`, `ipAllowList: []` (blocks all external connections), static `routes`/`headers`. | Documented |
| Deploy hooks | GET or POST; `?ref=<sha>` deploys a specific commit; 200 = started, 202 = queued; the URL is a secret. | Documented. Unverified: whether hooks work with auto-deploy off. |
| Static-site rewrite to the API | The destination may be a full public URL, and the rewrite serves it at the original path. Pass the wildcard on (`/api/*` -> `https://.../*`). POST through a rewrite is not documented. | **Unverified.** The smoke test checks a POST. |
| Client IP behind Render's proxy | Community report: Render *appends* to `X-Forwarded-For` and does not reset it. | Unverified (see "Proxy and rate limiting") |
| Free tier | Free web services sleep when idle. Free Postgres instances expire after a fixed period. | Check current plan limits before the demo date |

Sources: [Render database credentials](https://render.com/docs/postgresql-credentials),
[Blueprint spec](https://render.com/docs/blueprint-spec),
[Deploy hooks](https://render.com/docs/deploy-hooks),
[Redirects and rewrites](https://render.com/docs/redirects-rewrites),
[Render feedback: X-Forwarded-For](https://feedback.render.com/features/p/send-the-correct-xforwardedfor),
[Render community: rewrite wildcard](https://community.render.com/t/rewrite-rules-giving-issue/8187).

### If the default user lacks CREATEROLE

Stop. There is then no safe way on Render to give the API a SELECT-only
login: dashboard-created users are full owners, and the API refuses to start
with one. The options are:
(a) ask Render support whether a restricted role can be created;
(b) host the demo database with a provider that allows role creation;
(c) drop the public demo and present only local Docker Compose.
Do not weaken the startup privilege check.

## Proxy and rate limiting

- `backend/app/limits.py` keys per-client limits on the ASGI client address
  and never reads `X-Forwarded-For` itself.
- uvicorn (0.54, `backend/Dockerfile` command) rewrites the client address
  only for connections from trusted proxies, by default only 127.0.0.1. It
  then takes the **rightmost untrusted** `X-Forwarded-For` entry. That entry
  is the one the proxy appended, so a client cannot spoof it.
- **Never set `--forwarded-allow-ips="*"` or `FORWARDED_ALLOW_IPS=*`.**
  With `*`, uvicorn uses the **leftmost** entry. The client chooses that
  entry, so anyone could bypass the per-client limit.
- Expected on Render: Render's proxy does not connect from 127.0.0.1, so the
  API sees the proxy's address as the client. All visitors then share one
  per-client budget (10 resume matches and 120 other requests per minute).
  This fails safe: it throttles harder, never less, and the global budget
  still caps total load. For a low-traffic demo this is acceptable.
  Requests through the static-site rewrite gain one more proxy hop.
- Counters are in memory and per process. They reset on every deploy or
  restart.
- Verify after deploying (step 10).
- Follow-up only if the shared budget turns out too strict: add an opt-in
  setting that takes the client from the Nth-from-right `X-Forwarded-For`
  entry. It needs its own review and tests.

## Release procedure

Every step marked **[approval]** needs your explicit go-ahead at the time.

1. **[approval] Merge the reviewed changes to `main`.**
   - Check that CI is green.
   - Fill in the API's real onrender.com host in `render.yaml` if Render
     assigns a different name.

2. **[approval] Create the Render resources from the Blueprint**
   (Dashboard -> New -> Blueprint -> this repository).
   - When prompted for `CAREERPILOT_DEMO_DATABASE_URL`, leave it empty for
     now.
   - The initial deploy then refuses to start the API, which is fail-closed
     and expected.
   - The static site goes live showing "server mode could not be
     confirmed", with all write actions hidden.

3. **[approval] Read-only capability check.**
   - **Current state:** blocked. The external connection failed with
     `FATAL: SCRAM channel binding check failed` (see "Current status").
     Do not continue past this step until Render Support confirms
     authentication and the role.
   - In the database's Networking settings, temporarily add your own
     public IP as a `/32` to the allowlist.
   - Connect with the *external* owner URL (TLS is enforced by Render).
     Type the password at the prompt, not into the shell history:

         psql "host=<external host> port=5432 dbname=careerpilot_demo user=careerpilot_owner sslmode=require" -X

         SELECT current_user, current_database(),
                current_setting('server_version') AS version,
                r.rolsuper, r.rolcreaterole, r.rolcreatedb,
                (SELECT datdba::regrole::text FROM pg_database
                  WHERE datname = current_database()) AS database_owner,
                (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()) AS tls,
                current_setting('createrole_self_grant') AS self_grant
           FROM pg_roles r WHERE r.rolname = current_user;

   - Proceed only if all of these hold:
     - user `careerpilot_owner`, database `careerpilot_demo`, version 16.x;
     - `rolsuper = f` and `rolcreaterole = t`;
     - `database_owner = careerpilot_owner` and `tls = t`.
   - Otherwise see "If the default user lacks CREATEROLE".

4. **[approval] Stage the SQL.**
   - Copy `deploy/render/*.sql.review` to a staging directory as `.sql`,
     byte-identical, and record their SHA-256 hashes. The `\ir` include
     resolves only after this step.

5. **[approval] Create the schema and the role, in one session each:**

       psql "<same connection string>" -X -v ON_ERROR_STOP=1 -f 01_render_schema.sql
       psql "<same connection string>" -X -v ON_ERROR_STOP=1 -f 02_render_demo_role.sql

   - Script 02 includes 03 and commits only if every check passes.
   - Expect one NOTICE about large-object functions. It is a documented
     residual risk: only Render's superuser can revoke them.

6. **[approval] Set the reader's password**, interactively. The input is
   hidden and sent as a SCRAM hash, so it never appears in a statement log.

       psql "<same connection string>" -X -c "\password careerpilot_demo_reader"

   - Generate a long random password, and keep it only in your password
     manager and in Render.

7. **[approval] Seed fictional data.** Run a dry run first, then apply:

       CAREERPILOT_SEED_DATABASE_URL="postgresql://careerpilot_owner:<password>@<external host>/careerpilot_demo" \
         python -m backend.scripts.seed_demo_data \
           --expect-database careerpilot_demo \
           --expect-host <external host> --expect-user careerpilot_owner
       # then the same with: --apply --confirm careerpilot_owner@<external host>/careerpilot_demo

   - The script refuses anything else: a database other than
     `careerpilot_demo`, a mismatched host or user, no TLS, a superuser,
     PostgreSQL other than 16, or a table with non-seed rows.
   - Set the variable only for this command, and clear it afterwards.

8. **[approval] Close the database again.**
   - Remove your `/32` from the allowlist.
   - Re-run the read-only verifier first if you like:

         psql ... -c "BEGIN READ ONLY" -f 03_render_demo_role_verify.sql -c "ROLLBACK"

9. **[approval] Configure the API and the release workflow.**
   - In Render, set `CAREERPILOT_DEMO_DATABASE_URL` to the **internal**
     database URL with the reader's credentials:
     `postgresql://careerpilot_demo_reader:<password>@<internal host>:5432/careerpilot_demo`
   - In GitHub, create the environment `production` **before** the first
     run. Add yourself as required reviewer, and set its deployment
     branches to `main` only. If the environment does not exist, GitHub
     creates it on first use *without* protection rules, so there would be
     no approval pause.
   - Add `RENDER_API_DEPLOY_HOOK` and `RENDER_WEB_DEPLOY_HOOK` (from each
     service's Settings) as **environment secrets of `production` only**.
     Never add them as repository secrets: those reach the deploy job
     whether or not the environment is protected.
   - Add `RENDER_API_URL` and `RENDER_WEB_URL` as **repository variables**.
     They are public URLs, and the smoke job does not run in the
     environment, so it cannot read environment variables.

10. **[approval] Release.**
    - Actions -> Deploy -> Run workflow on `main`, type `DEPLOY`, then
      approve the `production` gate.
    - Confirm in the Render dashboard that both services run the expected
      commit.
    - The smoke job then checks:
      - `/health`, and that `/config` reports `public_demo` read-only;
      - 403 for POST, PATCH and DELETE, directly and through the rewrite;
      - `/dashboard` 200, and the rewrite forwards GET and POST;
      - 413 for an oversized body, and 429 under a burst.
    - Also check manually:
      - the API log shows the public_demo startup warning and no privilege
        errors;
      - the web UI shows the read-only banner and the fictional records;
      - from a second network (for example a phone), resume matching is
        still throttled while the first client is limited. That confirms
        the shared-budget behavior described above. Sending a forged
        `X-Forwarded-For` header must not reset your limit.

## Rollback and emergency stop

- **Bad release:** in the Render dashboard, open the service and roll back
  to the previous deploy. Then fix forward through a reviewed change and a
  new release.
- **Stop the demo immediately:** suspend `careerpilot-api` (and
  `careerpilot-web` if needed) in the dashboard. Suspended services serve
  nothing.
- **Credential leak:**
  - Reader password: suspend the API, set a new password with
    `\password careerpilot_demo_reader`, and update the Render variable.
  - Deploy hook: click "Regenerate Hook" and update the GitHub secret.
  - Owner credentials: rotate them as described in Render's credentials
    documentation.
- **Data:** the database holds only fictional seed rows. Re-running the seed
  restores them, because it is idempotent and never deletes. Removing data,
  dropping roles, or deleting the database are destructive operations; each
  needs separate approval.

## Known residual risks

- The large-object creation functions stay executable by PUBLIC on Render
  (see 02/03). The API exposes no SQL, and sessions start read-only.
- The rate limiter's per-client budget is probably shared by all visitors
  (see above).
- Grants changed after startup are detected only on the next restart.
- The free tier sleeps and expires (see the findings table).
