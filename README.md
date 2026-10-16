# CareerPilot
AI-assisted job application tracking and career preparation platform

## CI/CD

GitHub Actions runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml) on pushes and pull requests to `main`, and on demand via **Run workflow** (`workflow_dispatch`).

| Job | What it checks |
|---|---|
| Backend tests | Installs `backend/requirements.txt` on Python 3.12, starts a PostgreSQL 16 service, creates `careerpilot_test`, and runs `python -m pytest backend/tests` |
| Frontend | `npm ci`, `npm run lint`, and `npm run build` on Node.js 24 |
| Docker build | Validates `docker-compose.yml` and builds the backend and frontend images |

The pipeline uses temporary CI-only database credentials, a read-only `GITHUB_TOKEN`, and no repository secrets. It does not push images or deploy; deployment will be added in a later stage.

To run the same checks locally (tests use only the `careerpilot_test` database, never the development database):

```bash
python -m pytest backend/tests        # from the repository root
cd frontend && npm ci && npm run lint && npm run build
```
