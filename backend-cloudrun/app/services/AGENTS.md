# Services Agent Guide

## Scope

Service modules contain business workflows for AI reports, alarms, data analysis, video evidence, self-inspection, notification, scheduling, and external integrations.

## Rules

- Keep business rules here instead of embedding them in routers.
- Make fallback and missing-data behavior explicit, especially in AI reports and monitoring summaries.
- Do not let video risk language become a regulatory/legal conclusion.
- Keep long-running or network-facing work isolated and testable.

## Testing

- Add focused pytest coverage for calculations, report shape, fallback paths, scope rules, and integration adapters.
- Mock external LLM/SMS/COS/email services in tests.
