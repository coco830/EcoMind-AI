from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.openapi import auth as openapi_auth
from app.api.openapi import integration_tools


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def first(self):
        return self._value


class _FakeSummaryDB:
    def __init__(self, device):
        self.device = device

    async def execute(self, stmt):
        return _FakeScalarResult(self.device)


class _FakePushDB:
    def __init__(self):
        self.obj = None

    def add(self, obj):
        self.obj = obj

    async def flush(self):
        if self.obj is None:
            return
        if getattr(self.obj, "id", None) is None:
            self.obj.id = uuid4()
        now = datetime(2026, 4, 13, 21, 0, 0)
        if getattr(self.obj, "created_at", None) is None:
            self.obj.created_at = now
        self.obj.updated_at = now

    async def refresh(self, obj):
        return None


class _FakePushStatusDB:
    def __init__(self, push_job):
        self.push_job = push_job

    async def execute(self, stmt):
        return _FakeScalarResult(self.push_job)


class _FakeCosObject:
    def __init__(self, uri: str):
        self.uri = uri


class _FakeCosStorage:
    def build_key(self, *, org_id: str, filename: str) -> str:
        return f"push-jobs/{org_id}/{filename}"

    def put_bytes(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str = "application/octet-stream",
        content_disposition_filename: str | None = None,
    ) -> _FakeCosObject:
        return _FakeCosObject(uri=f"cos://test-bucket/{key}")


def _build_single_org_ctx(org_id: UUID):
    return SimpleNamespace(
        client=SimpleNamespace(id=uuid4()),
        org_id=org_id,
        org_name="测试企业",
        is_all_orgs=False,
    )


def _build_all_orgs_ctx(org_id: UUID):
    return SimpleNamespace(
        client=SimpleNamespace(id=uuid4()),
        org_id=org_id,
        org_name="平台管理员组织",
        is_all_orgs=True,
    )


def test_monitoring_summary_endpoint_accepts_mn_code_and_date_range(monkeypatch) -> None:
    org_id = UUID("00000000-0000-0000-0000-000000000123")
    fake_device = SimpleNamespace(mn="MN001", name="总排口数采仪")
    fake_db = _FakeSummaryDB(device=fake_device)

    async def override_db():
        yield fake_db

    async def fake_get_period_summary(self, *, device_id, org_id, start_time, end_time):
        return {
            "pollutant_count": 2,
            "total_data_points": 576,
            "items": [
                {
                    "pollutantCode": "w01018",
                    "pollutantName": "化学需氧量(CODcr)",
                    "unit": "mg/L",
                    "averageValue": 23.4,
                    "minValue": 19.1,
                    "maxValue": 31.7,
                    "completenessRate": 98.6,
                    "dataPoints": 288,
                    "firstSampleTime": "2026-04-01 00:00:00",
                    "lastSampleTime": "2026-04-01 23:55:00",
                },
                {
                    "pollutantCode": "w21003",
                    "pollutantName": "氨氮",
                    "unit": "mg/L",
                    "averageValue": 2.8,
                    "minValue": 1.9,
                    "maxValue": 3.4,
                    "completenessRate": 97.9,
                    "dataPoints": 288,
                    "firstSampleTime": "2026-04-01 00:00:00",
                    "lastSampleTime": "2026-04-01 23:55:00",
                },
            ],
        }

    monkeypatch.setattr(
        integration_tools.MonitoringService,
        "get_period_summary",
        fake_get_period_summary,
    )

    app = FastAPI()
    app.include_router(integration_tools.router, prefix="/openapi")
    app.dependency_overrides[openapi_auth.get_api_client] = lambda: _build_single_org_ctx(org_id)
    app.dependency_overrides[integration_tools.get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/openapi/monitoring/summary",
        json={
            "mnCode": "MN001",
            "startDate": "2026-04-01",
            "endDate": "2026-04-30",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["mnCode"] == "MN001"
    assert payload["data"]["deviceName"] == "总排口数采仪"
    assert payload["data"]["pollutantCount"] == 2
    assert payload["data"]["items"][0]["pollutantCode"] == "w01018"


def test_package_push_endpoint_accepts_multipart_form(monkeypatch) -> None:
    org_id = UUID("00000000-0000-0000-0000-000000000123")
    fake_db = _FakePushDB()

    async def override_db():
        yield fake_db

    monkeypatch.setattr(
        integration_tools,
        "get_cos_storage",
        lambda: _FakeCosStorage(),
    )

    app = FastAPI()
    app.include_router(integration_tools.router, prefix="/openapi")
    app.dependency_overrides[openapi_auth.get_api_client] = lambda: _build_single_org_ctx(org_id)
    app.dependency_overrides[integration_tools.get_db] = override_db
    client = TestClient(app)

    response = client.post(
        "/openapi/package/push",
        data={
            "metadata": json.dumps(
                {
                    "jobId": "export_job_001",
                    "packageName": "企业A-站点B-执行包",
                    "enterprise": {"id": str(org_id), "name": "测试企业"},
                    "station": {"id": "station_001", "name": "总排口"},
                },
                ensure_ascii=False,
            ),
        },
        files={
            "package": ("bundle.zip", b"zip-binary-content", "application/zip"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["status"] == "accepted"
    assert payload["data"]["packageName"] == "企业A-站点B-执行包"
    assert payload["data"]["documentLink"].startswith("cos://test-bucket/")
    assert fake_db.obj is not None
    assert fake_db.obj.source_job_id == "export_job_001"


def test_package_push_status_endpoint_returns_latest_status(monkeypatch) -> None:
    org_id = UUID("00000000-0000-0000-0000-000000000123")
    push_job_id = UUID("00000000-0000-0000-0000-000000000456")
    fake_push_job = SimpleNamespace(
        id=push_job_id,
        org_id=org_id,
        source_job_id="export_job_001",
        package_name="企业A-站点B-执行包",
        file_name="bundle.zip",
        package_uri="cos://test-bucket/push-jobs/00000000-0000-0000-0000-000000000123/bundle.zip",
        document_link="cos://test-bucket/push-jobs/00000000-0000-0000-0000-000000000123/bundle.zip",
        metadata_json=json.dumps({"jobId": "export_job_001", "station": {"name": "总排口"}}, ensure_ascii=False),
        file_size=4096,
        file_sha256="abc123",
        content_type="application/zip",
        status="accepted",
        message="accepted",
        created_at=datetime(2026, 4, 13, 21, 0, 0),
        updated_at=datetime(2026, 4, 13, 21, 5, 0),
    )
    fake_db = _FakePushStatusDB(push_job=fake_push_job)

    async def override_db():
        yield fake_db

    app = FastAPI()
    app.include_router(integration_tools.router, prefix="/openapi")
    app.dependency_overrides[openapi_auth.get_api_client] = lambda: _build_single_org_ctx(org_id)
    app.dependency_overrides[integration_tools.get_db] = override_db
    client = TestClient(app)

    response = client.get(
        "/openapi/package/push/status",
        params={"pushJobId": str(push_job_id)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["pushJobId"] == str(push_job_id)
    assert payload["data"]["sourceJobId"] == "export_job_001"
    assert payload["data"]["status"] == "accepted"
    assert payload["data"]["metadata"]["station"]["name"] == "总排口"


def test_package_push_status_endpoint_requires_org_selector_for_all_orgs_source_job() -> None:
    org_id = UUID("00000000-0000-0000-0000-000000000999")

    async def override_db():
        yield _FakePushStatusDB(push_job=None)

    app = FastAPI()
    app.include_router(integration_tools.router, prefix="/openapi")
    app.dependency_overrides[openapi_auth.get_api_client] = lambda: _build_all_orgs_ctx(org_id)
    app.dependency_overrides[integration_tools.get_db] = override_db
    client = TestClient(app)

    response = client.get(
        "/openapi/package/push/status",
        params={"sourceJobId": "export_job_001"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error_code"] == "MISSING_ENTERPRISE_SELECTOR"
