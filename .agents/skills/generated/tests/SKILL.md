---
name: tests
description: "Skill for the Tests area of EcoMind-AI. 6 symbols across 1 files."
---

# Tests

6 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how test_monitoring_summary_endpoint_accepts_mn_code_and_date_range, test_package_push_endpoint_accepts_multipart_form, test_package_push_status_endpoint_returns_latest_status work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | _build_single_org_ctx, test_monitoring_summary_endpoint_accepts_mn_code_and_date_range, test_package_push_endpoint_accepts_multipart_form, test_package_push_status_endpoint_returns_latest_status, _build_all_orgs_ctx (+1) |

## Entry Points

Start here when exploring this area:

- **`test_monitoring_summary_endpoint_accepts_mn_code_and_date_range`** (Function) — `backend-cloudrun/tests/test_openapi_integration_endpoints.py:103`
- **`test_package_push_endpoint_accepts_multipart_form`** (Function) — `backend-cloudrun/tests/test_openapi_integration_endpoints.py:173`
- **`test_package_push_status_endpoint_returns_latest_status`** (Function) — `backend-cloudrun/tests/test_openapi_integration_endpoints.py:220`
- **`test_package_push_status_endpoint_requires_org_selector_for_all_orgs_source_job`** (Function) — `backend-cloudrun/tests/test_openapi_integration_endpoints.py:265`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `test_monitoring_summary_endpoint_accepts_mn_code_and_date_range` | Function | `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | 103 |
| `test_package_push_endpoint_accepts_multipart_form` | Function | `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | 173 |
| `test_package_push_status_endpoint_returns_latest_status` | Function | `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | 220 |
| `test_package_push_status_endpoint_requires_org_selector_for_all_orgs_source_job` | Function | `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | 265 |
| `_build_single_org_ctx` | Function | `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | 85 |
| `_build_all_orgs_ctx` | Function | `backend-cloudrun/tests/test_openapi_integration_endpoints.py` | 94 |

## How to Explore

1. `gitnexus_context({name: "test_monitoring_summary_endpoint_accepts_mn_code_and_date_range"})` — see callers and callees
2. `gitnexus_query({query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
