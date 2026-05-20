# CLAUDE.md - EcoMind-AI Project Context

Auto-generated from all feature plans. Last updated: 2025-11-24

## Project Overview

EcoMind-AI 是一个智慧环保 SaaS 平台，专注于环境监测数据采集、存储和分析。平台遵循"轻硬件、重软件、AI驱动"的设计理念。

## Active Technologies

- Python 3.11+ (后端), TypeScript/JavaScript (前端) (001-ecomind-mvp)

## Technology Stack

**Backend**:
- Python 3.11+ with FastAPI
- asyncio + uvloop for high-performance async
- Pydantic v2 for data validation
- TDengine for time-series data
- PostgreSQL for business data
- JWT authentication, SM4 encryption

**Frontend**:
- Vue 3 with Composition API
- Vite as build tool
- Element Plus UI components
- ECharts 5 for visualization
- Pinia for state management

## Project Structure

```text
EcoMind-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API endpoints
│   │   ├── core/            # Config, security, encryption
│   │   ├── db/              # Database connections
│   │   ├── gateway/         # TCP server for HJ 212
│   │   ├── models/          # SQLAlchemy + Pydantic models
│   │   └── services/        # Business logic
│   └── tests/               # Pytest tests
├── frontend/
│   ├── src/
│   │   ├── api/             # API clients
│   │   ├── views/           # Page components
│   │   ├── stores/          # Pinia stores
│   │   └── router/          # Vue Router
│   └── package.json
├── specs/                   # Feature specifications
└── docker-compose.yml
```

## Commands

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest

# Frontend
cd frontend && npm install
npm run dev
npm run lint

# Linting
ruff check . --fix
mypy backend/app
```

## Code Style

Python 3.11+ (后端):
- Type hints everywhere
- Async/await for I/O
- Pydantic for validation
- Structlog for logging

TypeScript/JavaScript (前端):
- Vue 3 Composition API
- TypeScript for type safety
- Element Plus components

## Key Components

1. **TCP Gateway** (`backend/app/gateway/`): HJ 212 protocol data collectors
2. **HJ 212 Parser** (`backend/app/gateway/hj212_parser.py`): Protocol parser
3. **SM4 Encryption** (`backend/app/core/encryption.py`): Data encryption
4. **Anomaly Detection** (`backend/app/services/anomaly_detection.py`): XGBoost AI

## API Endpoints

- `/api/v1/auth/` - Authentication (login, register, me)
- `/api/v1/devices/` - Device management CRUD
- `/api/v1/data/` - Monitoring data queries
- `/api/v1/alarms/` - Alarm management

## Ports

- 8000: Backend API
- 9999: TCP Gateway
- 3000: Frontend dev
- 6030: TDengine
- 5432: PostgreSQL

## Recent Changes

- 001-ecomind-mvp: Full stack implementation complete
- Backend: FastAPI + TDengine + PostgreSQL
- Frontend: Vue 3 + Element Plus + ECharts
- TCP Gateway: HJ 212 protocol support

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
