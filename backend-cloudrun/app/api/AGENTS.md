# API Agent Guide

## Scope

This directory contains HTTP contracts.

- `v1/` - enterprise console APIs using JWT/session-style auth.
- `openapi/` - API-key bridge for mini-programs, agents, and external systems.

## Rules

- Treat route signatures, response fields, status codes, and auth dependencies as API contracts.
- For `/openapi/*`, always preserve `X-API-Key` behavior and organization scope checks.
- Keep routers thin. Move workflow logic into `app/services/`.
- Add regression tests under `backend-cloudrun/tests/` for behavior changes.

## Verification

```powershell
python .\verify.py test
python .\verify.py lsp
```
