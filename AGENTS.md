# EcoMind-AI Agent Guide

## Project Purpose

EcoMind-AI is an enterprise environmental operations platform. It combines monitoring data, device status, alarms, AI reports, video evidence, self-inspection materials, and external OpenAPI integrations so enterprises can detect environmental compliance risk before it becomes an enforcement issue.

This repository is not a regulator replacement system. Keep wording and behavior aligned with enterprise risk assistance: risk level, evidence, related monitoring data, and suggested action.

## Working Rules

- Do not work directly on `main`, `master`, `dev`, `develop`, or `trunk`.
- Use a task branch for documentation, guardrail, or low-risk maintenance work.
- Use a worktree for database migrations, cross-module behavior changes, auth/security changes, or large frontend/backend integration work.
- Do not commit `.env`, logs, generated build output, local databases, or dependency folders.
- Business behavior changes need a regression test or a minimal reproducible verification path before implementation.
- Business workflows, AI output, reports, compliance wording, and domain judgement changes need a matching `specs/**/*.feature` scenario before implementation.
- Merges to `main` require human approval.

## Project Map

- `backend-cloudrun/` - FastAPI backend, OpenAPI bridge, AI/report services, persistence, gateway helpers, Alembic migrations.
- `frontend/` - Vue 3 enterprise console.
- `ecosense-login/` - React/Vite login or entry shell.
- `docs/` - product, integration, architecture, and operating documentation.
- `specs/` - historical and active feature specs.
- `deploy/` - deployment notes and environment materials.
- `CODEMAP.md` - module map and dependency boundaries for agents.
- `docs/ARCHITECTURE.md` - architecture narrative and system boundaries.
- `docs/LSP.md` - editor and language-server setup.
- `docs/GIT_HOOKS.md` - project hook behavior.

## Verification

Prefer the unified project entry:

```powershell
python .\verify.py check
python .\verify.py spec
python .\verify.py test
python .\verify.py lsp
python .\verify.py all
```

`spec` parses `specs/**/*.feature` with `gherkin-v39`. `check` is intended for pre-push use and includes the spec gate plus low-cost syntax/type/test gates where local dependencies are available.

## BDD And Domain Capture

- `specs/**/*.feature` - machine-parseable Gherkin behavior contracts.
- `specs/**/*.feature.md` - human/AI-readable behavior notes, business context, business rules, forbidden behavior, and domain rationale.
- `specs/_glossary.md` - confirmed terms only.
- `specs/_open-questions.md` - unresolved business rules and domain decisions.

Domain capture priority:

1. Concrete feature behavior goes in `specs/**/*.feature.md`.
2. Term definitions go in `specs/_glossary.md`.
3. Unconfirmed business questions go in `specs/_open-questions.md`.
4. Stable cross-module decisions move to `docs/adr/` or `docs/domain/`.

## Domain Guardrails

- Video evidence supports risk review and evidence closure; it must not be presented as a legal monitoring conclusion.
- AI reports must be transparent about missing, fallback, interpolated, or substitute data.
- `single_org` API keys must stay scoped to one organization.
- `all_orgs` API keys require explicit organization filtering in external queries.
- Device, alarm, report, and video evidence changes can affect compliance workflows; keep tests close to the changed contract.

## Context Maintenance

- Root `AGENTS.md` holds repository-wide rules only.
- `specs/` holds BDD behavior specs, the domain glossary, and open business questions.
- Child `AGENTS.md` files hold local constraints for important folders.
- Keep `CODEMAP.md` current when module boundaries, data ownership, or important call paths change.
- Keep `docs/ARCHITECTURE.md` current when deployment shape, API boundaries, or persistence responsibilities change.
