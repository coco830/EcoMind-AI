---
name: models
description: "Skill for the Models area of EcoMind-AI. 79 symbols across 18 files."
---

# Models

79 symbols | 18 files | Cohesion: 99%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how OpenApiError, OrganizationWithStats, AlarmCreate work
- Modifying models-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/models/self_inspection.py` | SelfInspectionDataCreate, SelfInspectionDataResponse, SelfInspectionReportCreate, SelfInspectionReportUpdate, SelfInspectionReportResponse (+17) |
| `backend-cloudrun/app/models/video.py` | VideoChannelCreate, VideoChannelUpdate, VideoChannelResponse, VideoEventCreate, VideoEventResponse (+5) |
| `backend-cloudrun/app/models/monitoring_mysql.py` | MonitoringDataMySQLCreate, MonitoringDataMySQLResponse, MonitoringDailyStatsResponse, HeatmapDataPoint, MonitoringDataMySQL (+2) |
| `backend-cloudrun/app/models/monitoring.py` | MonitoringDataCreate, MonitoringData, MonitoringDataResponse, MonitoringDataQuery, MonitoringDataStats |
| `backend-cloudrun/app/models/password_reset.py` | ForgotPasswordRequest, ResetPasswordRequest, ForgotPasswordResponse, ResetPasswordResponse, PasswordResetToken |
| `backend-cloudrun/app/models/invitation.py` | InvitationCodeCreate, InvitationCodeResponse, InvitationCodeUpdate, InvitationCode |
| `backend-cloudrun/app/models/user.py` | UserCreate, UserInDB, UserResponse, User |
| `backend-cloudrun/app/models/alarm.py` | AlarmCreate, AlarmResponse, Alarm |
| `backend-cloudrun/app/models/api_client.py` | ApiClientCreate, ApiClientResponse, ApiClient |
| `backend-cloudrun/app/models/daily_report.py` | DailyReportCreate, DailyReportResponse, DailyReport |

## Entry Points

Start here when exploring this area:

- **`OpenApiError`** (Class) — `backend-cloudrun/app/api/openapi/schemas.py:27`
- **`OrganizationWithStats`** (Class) — `backend-cloudrun/app/api/v1/organizations.py:40`
- **`AlarmCreate`** (Class) — `backend-cloudrun/app/models/alarm.py:86`
- **`AlarmResponse`** (Class) — `backend-cloudrun/app/models/alarm.py:98`
- **`ApiClientCreate`** (Class) — `backend-cloudrun/app/models/api_client.py:60`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `OpenApiError` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 27 |
| `OrganizationWithStats` | Class | `backend-cloudrun/app/api/v1/organizations.py` | 40 |
| `AlarmCreate` | Class | `backend-cloudrun/app/models/alarm.py` | 86 |
| `AlarmResponse` | Class | `backend-cloudrun/app/models/alarm.py` | 98 |
| `ApiClientCreate` | Class | `backend-cloudrun/app/models/api_client.py` | 60 |
| `ApiClientResponse` | Class | `backend-cloudrun/app/models/api_client.py` | 70 |
| `BaseSchema` | Class | `backend-cloudrun/app/models/base.py` | 8 |
| `DailyReportCreate` | Class | `backend-cloudrun/app/models/daily_report.py` | 85 |
| `DailyReportResponse` | Class | `backend-cloudrun/app/models/daily_report.py` | 92 |
| `DeviceCreate` | Class | `backend-cloudrun/app/models/device.py` | 249 |
| `DeviceResponse` | Class | `backend-cloudrun/app/models/device.py` | 265 |
| `PackagePushJobResponse` | Class | `backend-cloudrun/app/models/integration_push_job.py` | 75 |
| `InvitationCodeCreate` | Class | `backend-cloudrun/app/models/invitation.py` | 77 |
| `InvitationCodeResponse` | Class | `backend-cloudrun/app/models/invitation.py` | 95 |
| `InvitationCodeUpdate` | Class | `backend-cloudrun/app/models/invitation.py` | 120 |
| `MonitoringDataCreate` | Class | `backend-cloudrun/app/models/monitoring.py` | 12 |
| `MonitoringData` | Class | `backend-cloudrun/app/models/monitoring.py` | 24 |
| `MonitoringDataResponse` | Class | `backend-cloudrun/app/models/monitoring.py` | 35 |
| `MonitoringDataQuery` | Class | `backend-cloudrun/app/models/monitoring.py` | 46 |
| `MonitoringDataStats` | Class | `backend-cloudrun/app/models/monitoring.py` | 56 |

## How to Explore

1. `gitnexus_context({name: "OpenApiError"})` — see callers and callees
2. `gitnexus_query({query: "models"})` — find related execution flows
3. Read key files listed above for implementation details
