# EcoMind-AI Code Map

## System Shape

EcoMind-AI is a multi-surface product:

- FastAPI backend exposes enterprise APIs, external OpenAPI bridge endpoints, AI report generation, monitoring data access, alarm handling, self-inspection workflows, and video evidence workflows.
- Vue console provides the main enterprise operations UI.
- React/Vite login shell provides a smaller entry experience.
- Docs/specs preserve product decisions and integration contracts.

## Root Modules

| Path | Role | Notes |
| --- | --- | --- |
| `backend-cloudrun/app/main.py` | FastAPI application entry | Mounts `/api/v1` and `/openapi`, configures CORS, scheduler, rate limiter, startup bootstrap. |
| `backend-cloudrun/app/api/v1/` | Enterprise console API | JWT-authenticated operational endpoints for devices, data, alarms, reports, video, organizations, invitations, auth. |
| `backend-cloudrun/app/api/openapi/` | External bridge API | API-key authenticated endpoints for mini-programs, agents, and external systems. |
| `backend-cloudrun/app/services/` | Business services | AI reports, alarms, monitoring analysis, video risk, notifications, self-inspection, schedulers. |
| `backend-cloudrun/app/models/` | ORM/data models | Organization, users, devices, monitoring, alarms, video, reports, API clients. |
| `backend-cloudrun/app/db/` | Persistence clients | SQLAlchemy async database setup and monitoring storage helpers. |
| `backend-cloudrun/app/gateway/` | Device ingestion helpers | HJ212 parsing and gateway/proxy utilities. |
| `backend-cloudrun/alembic/` | Database migrations | Treat migrations as high-risk, irreversible-ish changes. |
| `backend-cloudrun/tests/` | Backend regression tests | Current CI runs focused backend regression tests. |
| `frontend/src/` | Vue console source | Main business UI and API clients. |
| `ecosense-login/` | React login shell | Small Vite-based entry/login surface. |
| `docs/` | Documentation | Architecture, hooks, LSP, integrations, product decisions. |
| `docs/agents/` | Agent routing docs | Generated skills index for choosing project/user SOPs without reading every skill file. |
| `specs/` | Feature specs | BDD `.feature` files, domain glossary, open questions, and historical planning records. |
| `verify/` | Verification config | AFK testing config and report/schema templates. |
| `scripts/agent-ops/` | Agent operation scripts | Generates and checks `docs/agents/skills-index.md`. |
| `scripts/check_specs.py` | BDD parser gate | Runs `gherkin-v39` against `specs/**/*.feature` through `verify.py spec`. |

## Backend Call Paths

Enterprise console:

```text
frontend/src
  -> backend-cloudrun/app/api/v1/*
  -> backend-cloudrun/app/services/*
  -> backend-cloudrun/app/models + app/db/*
```

External bridge:

```text
external mini-program / agent
  -> /openapi/* with X-API-Key
  -> backend-cloudrun/app/api/openapi/*
  -> backend-cloudrun/app/services/*
```

AI report:

```text
reports/ai API
  -> services/report_service.py + services/ai_service.py
  -> monitoring data + alarm data + video_risk_service.py
  -> optional Spark LLM client
```

Video evidence:

```text
api/v1/video.py
  -> services/video_service.py + services/video_risk_service.py
  -> video models + alarm/report association
```

## Boundaries

- Keep legal/compliance wording conservative. The product helps enterprise operations identify risk; it does not replace official regulatory monitoring.
- Keep OpenAPI bridge access scope explicit. Do not let `single_org` keys cross organizations.
- Keep AI/report generation tolerant of missing data and explicit about fallback behavior.
- Keep Alembic migrations paired with tests or a clear manual verification plan.
- Avoid placing frontend-only presentation logic in backend services; backend should expose stable business fields and evidence links.

## Verification Entry Points

- `python .\verify.py check` - local pre-push gate.
- `python .\verify.py spec` - Gherkin parser gate for `specs/**/*.feature`.
- `python .\verify.py test` - backend regression tests.
- `python .\verify.py lsp` - Pyright and frontend type checks where dependencies are available.
- `python .\verify.py agents` - check generated agent skills index.
- `python .\verify.py agents --write` - regenerate `docs/agents/skills-index.md`.
- `python .\verify.py afk` - validate AFK test config and report templates.
- `python .\verify.py all` - complete local gate.
