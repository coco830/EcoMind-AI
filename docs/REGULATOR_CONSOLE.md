# Regulator Console - Scope and API Contract

This document defines the regulator-facing features, data scope rules, and API contracts.
All regulator endpoints return aggregated data only; no enterprise-level details are exposed.

## Scope Rules

- Role: `regulator` (derived from invitation code)
- Entry: unified login + invitation code registration
- Data access: aggregate only (no enterprise names, device IDs, coordinates, or raw values)
- Time delay: T+1 (default to yesterday)
- Sample threshold: per-industry minimum sample size, otherwise return "insufficient"

## Aggregation Dimensions

- Region: `region_code` / `park_code` (organization-level metadata)
- Industry: `industry_type` (organization or device fallback)
- Grid: H3 hexagon index (device lat/lng -> H3)

## Risk Score (v1)

Risk score is computed per organization and then aggregated:

```
risk_score = (
  exceed_rate * 0.4 +
  invalid_rate * 0.2 +
  offline_rate * 0.2 +
  alarm_device_rate * 0.2
) * 100
```

Risk levels (5 tiers):

- L1: 0-20
- L2: 20-40
- L3: 40-60
- L4: 60-80
- L5: 80-100

## API Contract (v1)

Base path: `/api/v1/regulator`

### GET /overview

Summary KPIs and distributions.

Query:
- `target_date` (YYYY-MM-DD, optional, default = yesterday)
- `region_code` (optional)
- `park_code` (optional)

Response:
```
{
  "target_date": "YYYY-MM-DD",
  "enterprise_count": 0,
  "device_count": 0,
  "online_device_count": 0,
  "offline_device_count": 0,
  "risk_distribution": [
    { "level": "L1", "count": 0 }
  ],
  "industry_distribution": [
    { "industry": "steel", "count": 0, "insufficient": false }
  ],
  "region_distribution": [
    { "region_code": "xxxx", "count": 0 }
  ]
}
```

### GET /heatmap

H3 grid risk heatmap.

Query:
- `target_date` (YYYY-MM-DD, optional)
- `resolution` (int, optional, default = 7)
- `region_code` (optional)
- `park_code` (optional)

Response:
```
{
  "target_date": "YYYY-MM-DD",
  "resolution": 7,
  "cells": [
    {
      "h3_index": "xxxx",
      "boundary": [[lng, lat], ...],
      "risk_level": "L3",
      "risk_score": 52.4,
      "enterprise_count": 12,
      "device_count": 34
    }
  ]
}
```

### GET /trends

Risk trend (daily or monthly).

Query:
- `start_date` (YYYY-MM-DD, optional)
- `end_date` (YYYY-MM-DD, optional)
- `granularity` ("daily" | "monthly", optional, default = "daily")

Response:
```
{
  "granularity": "daily",
  "series": [
    {
      "date": "YYYY-MM-DD",
      "risk_distribution": [
        { "level": "L1", "count": 0 }
      ]
    }
  ]
}
```

### GET /consistency

Self-inspection vs monitoring consistency summary.

Query:
- `start_date` (YYYY-MM-DD, optional)
- `end_date` (YYYY-MM-DD, optional)

Response:
```
{
  "summary": {
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "industry_breakdown": [
    { "industry": "steel", "high": 0, "medium": 0, "low": 0 }
  ],
  "region_breakdown": [
    { "region_code": "xxxx", "high": 0, "medium": 0, "low": 0 }
  ]
}
```

### GET /reports/download

Export aggregated regulator report in Excel or PDF.

Query:
- `report_type` ("daily" | "monthly")
- `target_date` (YYYY-MM-DD, if daily)
- `year` / `month` (if monthly)
- `format` ("excel" | "pdf")

Response: file stream
