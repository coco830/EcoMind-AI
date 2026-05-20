from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import ai as ai_api
from app.models.daily_report import DailyReport, ReportStatus
from app.services.data_analysis_service import DataAnalysisService
from app.services.data_interpolation import DataInterpolator, PredictionGranularity
from app.services.monitoring_service import MonitoringService


def _build_sample_monitoring_rows(
    target_date: date,
    pollutant_code: str = "w01018",
) -> list[dict[str, object]]:
    base = datetime.combine(target_date, datetime.min.time())
    rows: list[dict[str, object]] = []
    for i in range(0, 24 * 12, 2):
        rows.append(
            {
                "ts": base + timedelta(minutes=5 * i),
                "pollutant_code": pollutant_code,
                "value": float(30 + (i % 9)),
                "flag": "N",
            }
        )
    return rows


class _FakeSessionContext:
    def __init__(self, session: object | None = None):
        self.session = session if session is not None else object()

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeScalarResult:
    def __init__(self, value: object | None):
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _FakeDBSession:
    def __init__(self, report: DailyReport | None = None):
        self.report = report
        self.commit_count = 0

    async def execute(self, stmt) -> _FakeScalarResult:
        return _FakeScalarResult(self.report)

    def add(self, obj: DailyReport) -> None:
        self.report = obj

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, obj: object) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self, *sessions: object):
        self._sessions = list(sessions)

    def __call__(self) -> _FakeSessionContext:
        if self._sessions:
            session = self._sessions.pop(0)
        else:
            session = object()
        return _FakeSessionContext(session)


class _FakeSparkClient:
    async def chat(self, messages: list[dict[str, str]]) -> str:
        return "# 智能运维诊断日报\n\n系统运行正常。"

    async def chat_stream(self, messages: list[dict[str, str]]):
        yield "# 智能运维诊断日报"
        yield "\n\n系统运行正常。"


async def _fake_video_risk_assessment(*args, **kwargs) -> dict[str, object]:
    return {
        "enabled": True,
        "has_video_channels": True,
        "channel_count": 1,
        "ai_enabled_channel_count": 1,
        "event_count": 1,
        "evidence_count": 1,
        "linked_alarm_event_count": 1,
        "same_window_signal_count": 1,
        "overall_risk_level": "high",
        "overall_risk_label": "高风险",
        "overall_risk_score": 76,
        "summary": "检测到与数采同窗重合的视频异常证据。",
        "recommended_actions": ["立即复核排口现场并留样复测。"],
        "evidence_fragments": [
            {
                "event_id": "evt-1",
                "occurred_at": "2026-04-07T10:00:00",
                "channel_id": "channel-1",
                "channel_name": "废水总排口主视角",
                "point_type": "wastewater_outlet",
                "point_type_label": "废水总排口",
                "event_type": "wastewater_visual_anomaly",
                "level": "warning",
                "status": "pending",
                "title": "排口颜色短时变深",
                "summary": "颜色异常",
                "snapshot_uri": "https://example.com/snapshot.jpg",
                "clip_uri": "https://example.com/clip.mp4",
                "risk_level": "high",
                "risk_label": "高风险",
                "risk_score": 76,
                "associated_monitoring": [],
                "associated_data_summary": "w01018 时间窗最大值 45.2，接近阈值 50.0",
                "data_confirmed": True,
                "suggested_action": "立即复核排口现场并留样复测。",
                "related_alarm_id": "alarm-1",
            }
        ],
    }


def test_ai_report_http_chain_handles_pandas_3_hour_frequency(monkeypatch) -> None:
    target_date = date(2026, 4, 7)
    sample_rows = _build_sample_monitoring_rows(target_date)

    async def fake_query_monitoring_data(
        self,
        device_id=None,
        pollutant_code=None,
        start_time=None,
        end_time=None,
        limit=10000,
        **kwargs,
    ):
        return sample_rows

    async def fake_get_device_thresholds(self, device_id):
        return None

    async def fake_get_device_industry_info(self, device_id):
        return {
            "industry_type": "municipal_wastewater",
            "national_standard": "GB 18918-2002",
        }

    monkeypatch.setattr(
        MonitoringService,
        "query_monitoring_data",
        fake_query_monitoring_data,
    )
    monkeypatch.setattr(
        DataAnalysisService,
        "get_device_thresholds",
        fake_get_device_thresholds,
    )
    monkeypatch.setattr(
        DataAnalysisService,
        "get_device_industry_info",
        fake_get_device_industry_info,
    )
    monkeypatch.setattr(ai_api, "AsyncSessionLocal", lambda: _FakeSessionContext())
    monkeypatch.setattr(ai_api, "_get_spark_client", lambda: _FakeSparkClient())
    monkeypatch.setattr(ai_api, "_build_video_risk_assessment", _fake_video_risk_assessment)

    app = FastAPI()
    app.include_router(ai_api.router, prefix="/api/v1/ai")
    client = TestClient(app)

    sync_response = client.get(
        "/api/v1/ai/report/sync",
        params={
            "device_id": "DEV001",
            "device_name": "测试设备",
            "report_date": target_date.isoformat(),
        },
    )

    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["mode"] == "comprehensive"
    assert sync_payload["pollutant_count"] == 1
    assert sync_payload["stats"]["pollutants"][0]["hourly_stats"][0]["hour"] == "00:00"
    assert sync_payload["video_risk_assessment"]["overall_risk_level"] == "high"
    assert sync_payload["video_risk_assessment"]["evidence_fragments"][0]["channel_name"] == "废水总排口主视角"

    stream_response = client.get(
        "/api/v1/ai/report/stream",
        params={
            "device_id": "DEV001",
            "device_name": "测试设备",
            "report_date": target_date.isoformat(),
        },
    )

    assert stream_response.status_code == 200
    assert "event: done" in stream_response.text
    assert "event: error" not in stream_response.text
    assert '"video_risk_assessment"' in stream_response.text
    assert '"overall_risk_level": "high"' in stream_response.text


def test_data_interpolator_normalizes_legacy_hour_aliases() -> None:
    target_date = date(2026, 4, 7)
    sample_rows = _build_sample_monitoring_rows(target_date)

    interpolator = DataInterpolator(target_interval="1H")
    interpolated = interpolator.interpolate(sample_rows, target_interval="1H")
    prepared, metadata = interpolator.prepare_for_prediction(
        sample_rows,
        PredictionGranularity.HOURLY,
    )

    assert interpolator.target_interval == "1h"
    assert not interpolated.empty
    assert not prepared.empty
    assert metadata["interval"] == "1h"


def test_ai_report_generate_route_persists_video_risk_assessment(monkeypatch) -> None:
    target_date = date(2026, 4, 7)
    sample_rows = _build_sample_monitoring_rows(target_date)
    save_session = _FakeDBSession()

    async def fake_query_monitoring_data(
        self,
        device_id=None,
        pollutant_code=None,
        start_time=None,
        end_time=None,
        limit=10000,
        **kwargs,
    ):
        return sample_rows

    async def fake_get_device_thresholds(self, device_id):
        return None

    async def fake_get_device_industry_info(self, device_id):
        return {
            "industry_type": "municipal_wastewater",
            "national_standard": "GB 18918-2002",
        }

    monkeypatch.setattr(
        MonitoringService,
        "query_monitoring_data",
        fake_query_monitoring_data,
    )
    monkeypatch.setattr(
        DataAnalysisService,
        "get_device_thresholds",
        fake_get_device_thresholds,
    )
    monkeypatch.setattr(
        DataAnalysisService,
        "get_device_industry_info",
        fake_get_device_industry_info,
    )
    monkeypatch.setattr(
        ai_api,
        "AsyncSessionLocal",
        _FakeSessionFactory(object(), save_session),
    )
    monkeypatch.setattr(ai_api, "_get_spark_client", lambda: _FakeSparkClient())
    monkeypatch.setattr(ai_api, "_build_video_risk_assessment", _fake_video_risk_assessment)

    app = FastAPI()
    app.include_router(ai_api.router, prefix="/api/v1/ai")
    app.dependency_overrides[ai_api.get_current_active_user] = (
        lambda: SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000001"))
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/ai/report/generate",
        params={
            "device_id": "DEV001",
            "device_name": "测试设备",
            "report_date": target_date.isoformat(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["video_risk_assessment"]["overall_risk_level"] == "high"
    assert payload["rate_limit"]["user_daily_used"] == 1

    assert save_session.report is not None
    assert save_session.commit_count == 1
    snapshot = json.loads(save_session.report.stats_snapshot)
    assert snapshot["video_risk_assessment"]["overall_risk_label"] == "高风险"


def test_cached_report_exposes_video_risk_assessment_at_top_level(monkeypatch) -> None:
    target_date = date(2026, 4, 7)
    report = DailyReport(
        device_id=uuid4(),
        report_date=target_date,
        status=ReportStatus.COMPLETED.value,
        report_content="# 智能运维诊断日报\n\n系统运行正常。",
        stats_snapshot=json.dumps(
            {
                "pollutants": [
                    {
                        "pollutant_code": "w01018",
                        "hourly_stats": [{"hour": "00:00", "avg": 30.0}],
                    }
                ],
                "video_risk_assessment": {
                    "overall_risk_level": "high",
                    "overall_risk_label": "高风险",
                    "overall_risk_score": 76,
                },
            },
            ensure_ascii=False,
        ),
        pollutant_count=1,
        data_points=12,
        domain="water",
        generated_at=datetime(2026, 4, 7, 11, 0, 0),
    )
    report.created_at = datetime(2026, 4, 7, 11, 0, 0)

    monkeypatch.setattr(
        ai_api,
        "AsyncSessionLocal",
        _FakeSessionFactory(_FakeDBSession(report=report)),
    )

    app = FastAPI()
    app.include_router(ai_api.router, prefix="/api/v1/ai")
    app.dependency_overrides[ai_api.get_current_active_user] = (
        lambda: SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000001"))
    )
    client = TestClient(app)

    response = client.get(
        f"/api/v1/ai/report/cached/{report.device_id}",
        params={"report_date": target_date.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["exists"] is True
    assert payload["video_risk_assessment"]["overall_risk_level"] == "high"
    assert payload["video_risk_assessment"]["overall_risk_score"] == 76
