# Backend Agent Guide

## Scope

`backend-cloudrun` contains the FastAPI backend, persistence models, AI/report services, external OpenAPI bridge, device gateway helpers, migrations, and backend tests.

## Local Commands

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

From the repository root, prefer:

```powershell
python .\verify.py check
python .\verify.py test
python .\verify.py lsp
```

## Boundaries

- `app/api/v1/` is for JWT-authenticated enterprise console APIs.
- `app/api/openapi/` is for API-key authenticated external systems and agents.
- `app/services/` owns business workflows; keep routers thin.
- `app/models/` and `alembic/` changes are schema/data-contract changes and need stronger verification.
- `app/core/security.py`, `app/models/api_client.py`, and OpenAPI auth changes are security-sensitive.

## Testing Expectations

- Add or update pytest coverage for API behavior, report generation, alarm logic, OpenAPI scope handling, and regression fixes.
- Use focused tests first, then `python .\verify.py test`.
- Avoid requiring live cloud services in unit/regression tests.

## Domain Notes

- AI report output must disclose missing/fallback data.
- Video evidence is supporting evidence and risk context, not a legal conclusion.
- Keep organization scoping explicit in every externally callable path.
