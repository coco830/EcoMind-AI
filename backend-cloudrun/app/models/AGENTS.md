# Models Agent Guide

## Scope

This directory contains persistence models and business data structures.

## Rules

- Treat model fields as database and API-adjacent contracts.
- Schema changes usually require Alembic migrations and regression coverage.
- Preserve tenant/organization ownership fields and relationships.
- Avoid destructive data changes without an explicit migration and rollback/backup note.

## Verification

Run model/migration-related changes with:

```powershell
python .\verify.py test
python .\verify.py lsp
```
