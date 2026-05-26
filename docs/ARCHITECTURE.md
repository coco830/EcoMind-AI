# EcoMind-AI Architecture

## Purpose

EcoMind-AI is an enterprise environmental operations SaaS. It helps enterprises monitor online environmental data, review alarms, connect video evidence, generate AI-assisted reports, and expose controlled data bridges to mini-programs or agents.

The platform's product boundary is enterprise risk assistance. It does not replace official regulatory monitoring or legal conclusions.

## Runtime Components

```text
Vue enterprise console
  -> FastAPI /api/v1
  -> services
  -> SQLAlchemy models / database clients

External mini-programs and agents
  -> FastAPI /openapi with X-API-Key
  -> scoped services
  -> monitoring, alarm, report, package-push data

Device/gateway helpers
  -> HJ212/proxy utilities
  -> monitoring ingestion and status workflows
```

## Backend Layers

- `app/main.py` creates the FastAPI application, mounts routers, configures CORS/rate limiting, starts scheduler work, and runs startup bootstrap.
- `app/api/v1/` exposes enterprise console routes.
- `app/api/openapi/` exposes API-key bridge routes for external systems.
- `app/services/` contains report, alarm, video, monitoring, notification, LLM, and scheduling workflows.
- `app/models/` contains persistence models.
- `app/db/` owns database sessions and storage clients.
- `alembic/` owns database schema migration history.
- Production startup validates migrated database schema only; it does not run `create_all` or best-effort `ensure_*` schema mutations.

## Frontend Layers

- `frontend/` is the Vue 3 enterprise console.
- `ecosense-login/` is a smaller React/Vite login or entry shell.

Frontend surfaces should consume backend contracts rather than duplicating backend business rules.

## Data and Compliance Boundaries

- Organization and tenant scope must be preserved across API, service, and model layers.
- API-key scope for `/openapi/*` must be explicit.
- AI reports must disclose missing, fallback, interpolated, or substitute data.
- Video evidence supports risk review and evidence closure. It must not be described as official legal monitoring evidence by default.
- Database migrations are high-risk changes and need a clear verification path.

## Verification Architecture

`verify.py` is the local unified gate:

- `check` - compile Python, run focused backend regressions, and run available type checks.
- `test` - run backend pytest regressions.
- `lsp` - run Pyright and frontend type checks where local dependencies exist.
- `afk` - validate optional AFK testing config.
- `db` - run database bootstrap and production schema-mutation guardrail checks.
- `all` - run all local gates.

Git hooks call `python .\verify.py check` before push.
