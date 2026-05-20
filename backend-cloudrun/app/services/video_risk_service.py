from __future__ import annotations

"""Build lightweight video-risk assessments for AI reports."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import Device
from app.models.video import (
    VideoChannel,
    VideoEvent,
    VideoEventLevel,
    VideoEventStatus,
    VideoEventType,
    deserialize_video_extra_data,
)
from app.services.data_analysis_service import DataAnalysisService
from app.services.monitoring_service import MonitoringService

logger = structlog.get_logger(__name__)

WINDOW_MINUTES = 30
MAX_EVIDENCE_EVENTS = 3

LEVEL_BASE_SCORE = {
    VideoEventLevel.INFO.value: 18,
    VideoEventLevel.WARNING.value: 38,
    VideoEventLevel.CRITICAL.value: 60,
}

STATUS_SCORE = {
    VideoEventStatus.PENDING.value: 12,
    VideoEventStatus.ACKNOWLEDGED.value: 6,
    VideoEventStatus.RESOLVED.value: -6,
}

TYPE_SCORE = {
    VideoEventType.WASTEWATER_VISUAL_ANOMALY.value: 20,
    VideoEventType.SMOKE_PLUME_CHANGE.value: 20,
    VideoEventType.AI_LINKAGE.value: 12,
    VideoEventType.STREAM_OFFLINE.value: 12,
    VideoEventType.OCCLUSION.value: 10,
    VideoEventType.MANUAL_SAMPLING.value: 8,
    VideoEventType.INTRUSION.value: 10,
    VideoEventType.LOITERING.value: 6,
    VideoEventType.CUSTOM.value: 8,
}

POINT_TYPE_LABELS = {
    "station_room": "站房",
    "wastewater_outlet": "废水总排口",
    "wastegas_outlet": "废气总排口",
    "manual_sampling": "手工采样点",
    "custom": "自定义点位",
}

EVENT_ACTIONS = {
    VideoEventType.WASTEWATER_VISUAL_ANOMALY.value: (
        "立即复核排口现场、采样链路和前后30分钟数采曲线，必要时留样复测并核查工艺负荷。"
    ),
    VideoEventType.SMOKE_PLUME_CHANGE.value: (
        "立即核查废气治理设施运行参数、风机/喷淋/脱硫脱硝状态，并回看同窗烟羽变化。"
    ),
    VideoEventType.STREAM_OFFLINE.value: (
        "优先恢复视频链路并补充人工巡检记录，避免风险窗口缺少现场证据。"
    ),
    VideoEventType.OCCLUSION.value: (
        "检查镜头遮挡、补光和机位朝向，确保排口及采样区无遮挡、可清晰取证。"
    ),
    VideoEventType.MANUAL_SAMPLING.value: (
        "核对采样操作、留样记录和人员进出记录，确认操作过程与数据变化是否一致。"
    ),
    VideoEventType.AI_LINKAGE.value: (
        "结合触发告警的污染因子与视频片段复核现场，必要时立即安排当班人员到场确认。"
    ),
}


class VideoRiskService:
    """Summarize video evidence into lightweight enterprise-facing risk signals."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.monitoring_service = MonitoringService(db_session)
        self.data_analysis_service = DataAnalysisService(db_session)

    async def build_device_video_risk_assessment(
        self,
        *,
        device_id: str,
        target_date: date,
        stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        device = await self._resolve_device(device_id)
        channels = await self._list_channels(device)
        ai_enabled_channels = sum(1 for channel in channels if channel.ai_enabled)

        if not channels:
            return self._empty_assessment(
                has_video_channels=False,
                channel_count=0,
                ai_enabled_channel_count=0,
                summary="当前设备尚未配置视频通道，暂无法提供视频联动佐证。",
            )

        events = await self._list_events(device, target_date)
        if not events:
            return self._empty_assessment(
                has_video_channels=True,
                channel_count=len(channels),
                ai_enabled_channel_count=ai_enabled_channels,
                summary="当前设备已配置视频通道，但报告日期内未登记可用视频证据。",
            )

        daily_signal_map = self._build_daily_signal_map(stats or {})
        thresholds = await self.data_analysis_service.get_device_thresholds(
            device.mn if device else device_id
        )

        event_assessments: list[dict[str, Any]] = []
        confirmed_count = 0
        evidence_count = 0
        linked_alarm_count = 0

        for event in events[:MAX_EVIDENCE_EVENTS]:
            assessment = await self._build_event_assessment(
                device_id=device.mn if device else device_id,
                event=event,
                thresholds=thresholds,
                daily_signal_map=daily_signal_map,
            )
            if assessment["data_confirmed"]:
                confirmed_count += 1
            if assessment["snapshot_uri"] or assessment["clip_uri"]:
                evidence_count += 1
            if assessment["related_alarm_id"]:
                linked_alarm_count += 1
            event_assessments.append(assessment)

        max_score = max(item["risk_score"] for item in event_assessments)
        overall_score = min(
            100,
            max_score
            + min(12, (len(event_assessments) - 1) * 4)
            + min(8, confirmed_count * 4),
        )
        overall_level, overall_label = self._risk_level_from_score(overall_score)

        recommended_actions = self._collect_recommended_actions(event_assessments)
        summary = (
            f"今日共识别 {len(events)} 条视频联动事件，"
            f"纳入报告重点研判 {len(event_assessments)} 条；"
            f"其中 {confirmed_count} 条与数采异常同窗重合，"
            f"综合判定为{overall_label}。"
        )

        return {
            "enabled": True,
            "has_video_channels": True,
            "channel_count": len(channels),
            "ai_enabled_channel_count": ai_enabled_channels,
            "event_count": len(events),
            "evidence_count": evidence_count,
            "linked_alarm_event_count": linked_alarm_count,
            "same_window_signal_count": confirmed_count,
            "overall_risk_level": overall_level,
            "overall_risk_label": overall_label,
            "overall_risk_score": overall_score,
            "summary": summary,
            "recommended_actions": recommended_actions,
            "evidence_fragments": event_assessments,
        }

    @staticmethod
    def format_for_prompt(assessment: dict[str, Any]) -> str:
        """Format structured video assessment into a prompt-safe text block."""
        if not assessment.get("has_video_channels"):
            return "未配置视频通道，暂无视频联动佐证。"

        lines = [
            "## 视频联动风险摘要",
            f"- 综合疑似风险级别：{assessment.get('overall_risk_label', '无')}（{assessment.get('overall_risk_score', 0)}/100）",
            f"- 摘要：{assessment.get('summary', '无')}",
        ]

        actions = assessment.get("recommended_actions") or []
        if actions:
            lines.append("- 建议优先动作：")
            for action in actions[:3]:
                lines.append(f"  * {action}")

        evidence_fragments = assessment.get("evidence_fragments") or []
        if not evidence_fragments:
            lines.append("- 当日未登记可用视频事件。")
            return "\n".join(lines)

        lines.append("### 关键证据片段")
        for index, item in enumerate(evidence_fragments[:3], start=1):
            lines.append(f"- 证据{index}：{item['title']}")
            lines.append(f"  * 时间：{item['occurred_at']}")
            lines.append(
                f"  * 机位：{item['channel_name']}（{item['point_type_label']}）"
            )
            lines.append(
                f"  * 疑似风险：{item['risk_label']}（{item['risk_score']}/100）"
            )
            lines.append(
                f"  * 关联数采：{item['associated_data_summary']}"
            )
            lines.append(f"  * 建议动作：{item['suggested_action']}")

        lines.append(
            "### 额外约束\n"
            "1. 如果引用视频联动内容，只能基于以上摘要与证据，不得臆造画面细节。\n"
            "2. 对企业输出必须使用“疑似风险级别 + 证据片段 + 关联数采 + 建议动作”的表达。\n"
            "3. 视频摘要用于佐证和提前预警，不能替代法定浓度结论。"
        )
        return "\n".join(lines)

    async def _resolve_device(self, device_id: str) -> Device | None:
        result = await self.db_session.execute(
            select(Device).where((Device.id == device_id) | (Device.mn == device_id))
        )
        return result.scalar_one_or_none()

    async def _list_channels(self, device: Device | None) -> list[VideoChannel]:
        if device is None:
            return []

        result = await self.db_session.execute(
            select(VideoChannel)
            .where(VideoChannel.device_id == device.id)
            .order_by(VideoChannel.ai_enabled.desc(), VideoChannel.created_at.asc())
        )
        return result.scalars().all()

    async def _list_events(self, device: Device | None, target_date: date) -> list[VideoEvent]:
        if device is None:
            return []

        start_time = datetime.combine(target_date, datetime.min.time())
        end_time = datetime.combine(target_date, datetime.max.time())

        result = await self.db_session.execute(
            select(VideoEvent)
            .options(selectinload(VideoEvent.channel))
            .where(
                VideoEvent.device_id == device.id,
                VideoEvent.occurred_at >= start_time,
                VideoEvent.occurred_at <= end_time,
            )
            .order_by(VideoEvent.occurred_at.desc(), VideoEvent.created_at.desc())
        )
        events = result.scalars().all()
        return sorted(
            events,
            key=lambda item: (
                self._status_priority(item.status),
                self._level_priority(item.level),
                item.occurred_at,
            ),
            reverse=True,
        )

    async def _build_event_assessment(
        self,
        *,
        device_id: str,
        event: VideoEvent,
        thresholds: Any,
        daily_signal_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        monitoring_context = await self._build_monitoring_context(
            device_id=device_id,
            event=event,
            thresholds=thresholds,
            daily_signal_map=daily_signal_map,
        )
        score = self._score_event(event, monitoring_context)
        risk_level, risk_label = self._risk_level_from_score(score)

        channel = event.channel
        point_type = channel.point_type if channel else "custom"
        point_type_label = POINT_TYPE_LABELS.get(point_type, "视频点位")

        return {
            "event_id": str(event.id),
            "related_alarm_id": str(event.related_alarm_id) if event.related_alarm_id else None,
            "occurred_at": event.occurred_at.isoformat(),
            "channel_id": str(event.channel_id),
            "channel_name": channel.name if channel else "未知机位",
            "point_type": point_type,
            "point_type_label": point_type_label,
            "event_type": event.event_type,
            "level": event.level,
            "status": event.status,
            "title": event.title,
            "summary": event.summary,
            "snapshot_uri": event.snapshot_uri,
            "clip_uri": event.clip_uri,
            "risk_level": risk_level,
            "risk_label": risk_label,
            "risk_score": score,
            "associated_monitoring": monitoring_context["items"],
            "associated_data_summary": monitoring_context["summary"],
            "data_confirmed": monitoring_context["data_confirmed"],
            "suggested_action": self._build_action(event.event_type, monitoring_context),
        }

    async def _build_monitoring_context(
        self,
        *,
        device_id: str,
        event: VideoEvent,
        thresholds: Any,
        daily_signal_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        window_start = event.occurred_at - timedelta(minutes=WINDOW_MINUTES)
        window_end = event.occurred_at + timedelta(minutes=WINDOW_MINUTES)
        rows = await self.monitoring_service.query_monitoring_data(
            device_id=device_id,
            start_time=window_start,
            end_time=window_end,
            limit=2000,
        )

        items = self._summarize_rows_by_pollutant(rows, thresholds, daily_signal_map)
        if not items:
            items = self._build_alarm_fallback_items(
                event=event,
                thresholds=thresholds,
                daily_signal_map=daily_signal_map,
            )

        if not items:
            return {
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "items": [],
                "summary": "事件时间窗内无可用数采数据。",
                "data_confirmed": False,
            }

        data_confirmed = any(
            item.get("exceed_count", 0) > 0
            or item.get("near_threshold")
            or item.get("daily_over_limit_count", 0) > 0
            or item.get("daily_volatility", 0) >= 50
            for item in items
        )

        fragments = []
        for item in items[:2]:
            code = item["pollutant_code"]
            if item.get("exceed_count", 0) > 0 and item.get("threshold_value") is not None:
                fragments.append(
                    f"{code} 时间窗最大值 {item['window_max']:.2f}，已超过阈值 {item['threshold_value']}"
                )
            elif item.get("near_threshold") and item.get("threshold_value") is not None:
                fragments.append(
                    f"{code} 时间窗最大值 {item['window_max']:.2f}，接近阈值 {item['threshold_value']}"
                )
            else:
                fragments.append(
                    f"{code} 时间窗均值 {item['window_avg']:.2f}，日内波动 {item.get('daily_volatility', 0):.1f}%"
                )

        return {
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "items": items,
            "summary": "；".join(fragments),
            "data_confirmed": data_confirmed,
        }

    def _summarize_rows_by_pollutant(
        self,
        rows: list[dict[str, Any]],
        thresholds: Any,
        daily_signal_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            try:
                grouped[str(row["pollutant_code"])].append(float(row["value"]))
            except (KeyError, TypeError, ValueError):
                continue

        items: list[dict[str, Any]] = []
        for pollutant_code, values in grouped.items():
            if not values:
                continue
            threshold_value = None
            if thresholds:
                threshold = thresholds.get_threshold(pollutant_code)
                if threshold:
                    threshold_value = threshold.alarm_value
            exceed_count = (
                sum(1 for value in values if threshold_value is not None and value > threshold_value)
                if threshold_value is not None
                else 0
            )
            window_avg = sum(values) / len(values)
            window_max = max(values)
            daily_signal = daily_signal_map.get(pollutant_code, {})
            items.append(
                {
                    "pollutant_code": pollutant_code,
                    "window_avg": round(window_avg, 4),
                    "window_max": round(window_max, 4),
                    "window_min": round(min(values), 4),
                    "data_points": len(values),
                    "threshold_value": threshold_value,
                    "exceed_count": exceed_count,
                    "near_threshold": bool(
                        threshold_value is not None and threshold_value > 0 and window_max >= threshold_value * 0.9
                    ),
                    "daily_over_limit_count": int(daily_signal.get("over_limit_count", 0)),
                    "daily_volatility": float(daily_signal.get("volatility", 0.0)),
                    "daily_trend_description": daily_signal.get("trend_description"),
                }
            )

        return sorted(items, key=self._monitoring_item_priority, reverse=True)[:2]

    def _build_alarm_fallback_items(
        self,
        *,
        event: VideoEvent,
        thresholds: Any,
        daily_signal_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = deserialize_video_extra_data(event.extra_data)
        if not payload:
            return []

        pollutant_code = payload.get("pollutant_code")
        alarm_value = payload.get("alarm_value")
        if not pollutant_code or alarm_value is None:
            return []

        try:
            numeric_alarm_value = float(alarm_value)
        except (TypeError, ValueError):
            return []

        threshold_value = payload.get("threshold")
        if threshold_value is None and thresholds:
            threshold = thresholds.get_threshold(str(pollutant_code))
            if threshold:
                threshold_value = threshold.alarm_value

        daily_signal = daily_signal_map.get(str(pollutant_code), {})
        exceed_count = (
            1 if threshold_value is not None and numeric_alarm_value > float(threshold_value) else 0
        )
        return [
            {
                "pollutant_code": str(pollutant_code),
                "window_avg": round(numeric_alarm_value, 4),
                "window_max": round(numeric_alarm_value, 4),
                "window_min": round(numeric_alarm_value, 4),
                "data_points": 1,
                "threshold_value": threshold_value,
                "exceed_count": exceed_count,
                "near_threshold": bool(
                    threshold_value is not None and float(threshold_value) > 0 and numeric_alarm_value >= float(threshold_value) * 0.9
                ),
                "daily_over_limit_count": int(daily_signal.get("over_limit_count", 0)),
                "daily_volatility": float(daily_signal.get("volatility", 0.0)),
                "daily_trend_description": daily_signal.get("trend_description"),
            }
        ]

    def _build_daily_signal_map(self, stats: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for pollutant in stats.get("pollutants", []) or []:
            code = pollutant.get("pollutant_code")
            if not code:
                continue
            result[str(code)] = {
                "over_limit_count": pollutant.get("over_limit_count", 0),
                "volatility": pollutant.get("volatility", 0.0),
                "trend_description": pollutant.get("trend_description"),
            }
        return result

    def _score_event(self, event: VideoEvent, monitoring_context: dict[str, Any]) -> int:
        score = LEVEL_BASE_SCORE.get(event.level, 20)
        score += STATUS_SCORE.get(event.status, 0)
        score += TYPE_SCORE.get(event.event_type, 8)

        if event.related_alarm_id:
            score += 8
        if event.clip_uri:
            score += 5
        elif event.snapshot_uri:
            score += 3

        items = monitoring_context.get("items") or []
        if any(item.get("exceed_count", 0) > 0 for item in items):
            score += 18
        elif any(item.get("near_threshold") for item in items):
            score += 12
        elif any(item.get("daily_volatility", 0) >= 50 for item in items):
            score += 8

        return max(0, min(100, int(round(score))))

    def _build_action(self, event_type: str, monitoring_context: dict[str, Any]) -> str:
        base_action = EVENT_ACTIONS.get(
            event_type,
            "复核现场视频片段与同窗数采数据，并安排责任人完成当班排查。",
        )
        items = monitoring_context.get("items") or []
        if any(item.get("exceed_count", 0) > 0 for item in items):
            return base_action + " 当前已有同窗超标信号，建议立即升级为现场复核。"
        if any(item.get("near_threshold") for item in items):
            return base_action + " 当前同窗数据已接近阈值，建议加密巡检与留样。"
        return base_action

    def _collect_recommended_actions(self, event_assessments: list[dict[str, Any]]) -> list[str]:
        actions: list[str] = []
        for item in sorted(event_assessments, key=lambda data: data["risk_score"], reverse=True):
            action = item["suggested_action"]
            if action not in actions:
                actions.append(action)
        return actions[:3]

    def _risk_level_from_score(self, score: int) -> tuple[str, str]:
        if score >= 85:
            return "urgent", "紧急风险"
        if score >= 65:
            return "high", "高风险"
        if score >= 40:
            return "medium", "中风险"
        if score > 0:
            return "low", "低风险"
        return "none", "无视频风险"

    def _monitoring_item_priority(self, item: dict[str, Any]) -> tuple[float, float, float]:
        threshold_value = item.get("threshold_value")
        ratio = 0.0
        if threshold_value:
            try:
                ratio = float(item["window_max"]) / float(threshold_value)
            except (TypeError, ValueError, ZeroDivisionError):
                ratio = 0.0
        return (
            float(item.get("exceed_count", 0)),
            ratio,
            float(item.get("daily_volatility", 0.0)),
        )

    def _status_priority(self, status_value: str) -> int:
        if status_value == VideoEventStatus.PENDING.value:
            return 3
        if status_value == VideoEventStatus.ACKNOWLEDGED.value:
            return 2
        return 1

    def _level_priority(self, level_value: str) -> int:
        if level_value == VideoEventLevel.CRITICAL.value:
            return 3
        if level_value == VideoEventLevel.WARNING.value:
            return 2
        return 1

    def _empty_assessment(
        self,
        *,
        has_video_channels: bool,
        channel_count: int,
        ai_enabled_channel_count: int,
        summary: str,
    ) -> dict[str, Any]:
        return {
            "enabled": has_video_channels,
            "has_video_channels": has_video_channels,
            "channel_count": channel_count,
            "ai_enabled_channel_count": ai_enabled_channel_count,
            "event_count": 0,
            "evidence_count": 0,
            "linked_alarm_event_count": 0,
            "same_window_signal_count": 0,
            "overall_risk_level": "none",
            "overall_risk_label": "无视频风险",
            "overall_risk_score": 0,
            "summary": summary,
            "recommended_actions": [],
            "evidence_fragments": [],
        }
