# Database Automation Guardrails

## Startup Schema Policy

- `ENVIRONMENT=production` startup is read-only for schema. The backend runs a schema check and fails fast if required tables are missing.
- Production schema changes must be applied before startup with Alembic or another explicit migration process.
- Development and local test startup may still initialize an empty SQLite/MySQL/PostgreSQL database through `init_db()`.

## Default User Bootstrap

Startup default-user bootstrap and the initialization scripts never print plaintext passwords.

Production requires explicit password environment variables before creating or resetting default accounts:

- `DEFAULT_SUPERADMIN_PASSWORD`
- `DEFAULT_WENYUAN_PASSWORD`
- `DEFAULT_HUANBAO_PASSWORD`
- `SUPERADMIN_PASSWORD` for `scripts/init_superadmin.py` (or `DEFAULT_HUANBAO_PASSWORD` as a compatibility fallback)

If these variables are absent in production, bootstrap fails instead of falling back to built-in development passwords.

## Verification

Run the database automation guardrail checks from the repository root:

```powershell
python .\verify.py db
```

The check covers:

- Empty production database startup does not create tables.
- Empty development database initialization is idempotent.
- Production default-user initialization requires explicit passwords.
