"""AI analysis API endpoints."""

import asyncio
import json
import math
import random
from datetime import date, datetime, timedelta
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.anomaly_detection import detect_anomalies, IsolationForestDetector
from app.ai.prediction import predict_trend
from app.core.config import get_settings
from app.core.prompts import (
    build_expert_diagnosis_prompt,
    build_comprehensive_diagnosis_prompt,
    get_domain_from_pollutant_code,
    get_domain_knowledge,
    get_pollutant_info,
)
from app.db.tdengine_client import get_tdengine_client
from app.services.data_analysis_service import analyze_device_daily_stats
from app.services.llm.spark_client import SparkClient, SparkClientError

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()


class AnalyzeRequest(BaseModel):
    """Request body for analyze endpoint."""
    pollutant_code: str = Field(default="w01018", description="污染物代码 (默认: w01018/COD)")
    hours: int = Field(default=24, ge=1, le=168, description="分析时间范围 (小时)")


class AnomalyItem(BaseModel):
    """Single anomaly item in response."""
    timestamp: str | None
    value: float
    is_anomaly: bool
    anomaly_type: str
    anomaly_score: float
    flag: str | None
    reason: str | None


class AnalysisSummary(BaseModel):
    """Summary statistics for analysis."""
    total_anomalies: int
    by_type: dict[str, int]
    anomaly_rate: float = Field(description="异常率百分比")


class AnalyzeResponse(BaseModel):
    """Response for analyze endpoint."""
    device_id: str
    pollutant_code: str
    time_range: dict[str, str]
    total_points: int
    anomalies: list[AnomalyItem]
    summary: AnalysisSummary
    alarms_created: int = Field(default=0, description="创建的告警数量")
    message: str | None = None


class TestDetectionRequest(BaseModel):
    """Request body for test detection endpoint."""
    values: list[float] = Field(min_length=5, description="测试数据值列表 (至少5个)")
    flags: list[str] | None = Field(default=None, description="可选的标记列表")


class TestDetectionResponse(BaseModel):
    """Response for test detection endpoint."""
    total_points: int
    anomalies_detected: int
    results: list[AnomalyItem]
    summary: dict[str, int]


@router.post(
    "/analyze/{device_id}",
    response_model=AnalyzeResponse,
    summary="分析设备异常",
    description="使用 IsolationForest 算法分析指定设备的监测数据，识别异常值",
)
async def analyze_device(
    device_id: str,
    pollutant_code: str = Query(default="w01018", description="污染物代码"),
    hours: int = Query(default=24, ge=1, le=168, description="分析时间范围(小时)"),
    create_alarms: bool = Query(default=False, description="是否为检测到的异常创建告警"),
) -> dict[str, Any]:
    """Analyze device monitoring data for anomalies.

    Uses IsolationForest algorithm combined with rule-based detection:
    - Statistical outliers (IsolationForest)
    - Device faults (Flag = 'D')
    - Constant values (unchanged for > 1 hour)
    - Sudden spikes (> 3x std deviation)

    When create_alarms=True, alarms will be created for detected anomalies
    and stored in the database.
    """
    try:
        result = await detect_anomalies(
            device_id=device_id,
            pollutant_code=pollutant_code,
            hours=hours,
            create_alarms=create_alarms,
        )

        logger.info(
            "Device analysis completed",
            device_id=device_id,
            pollutant_code=pollutant_code,
            total_points=result.get("total_points", 0),
            anomalies=result.get("summary", {}).get("total_anomalies", 0),
        )

        return result

    except Exception as e:
        logger.error("Analysis failed", device_id=device_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {str(e)}",
        )


@router.post(
    "/test-detection",
    response_model=TestDetectionResponse,
    summary="测试异常检测",
    description="使用提供的测试数据验证异常检测算法",
)
async def test_detection(request: TestDetectionRequest) -> dict[str, Any]:
    """Test anomaly detection with custom data.

    Useful for validating the detection algorithm with known anomaly patterns.
    """
    from datetime import datetime, timedelta

    # Build test data with timestamps
    now = datetime.utcnow()
    test_data = []

    flags = request.flags or ["N"] * len(request.values)
    if len(flags) < len(request.values):
        flags.extend(["N"] * (len(request.values) - len(flags)))

    for i, (value, flag) in enumerate(zip(request.values, flags)):
        test_data.append({
            "ts": now - timedelta(minutes=len(request.values) - i),
            "value": value,
            "flag": flag,
        })

    # Run detection
    detector = IsolationForestDetector()
    results = detector.detect_anomalies(test_data)

    # Convert to response format
    anomaly_items = [
        {
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "value": r.value,
            "is_anomaly": r.is_anomaly,
            "anomaly_type": r.anomaly_type.value,
            "anomaly_score": r.anomaly_score,
            "flag": r.flag,
            "reason": r.reason,
        }
        for r in results
    ]

    # Count by type
    type_counts: dict[str, int] = {}
    for r in results:
        if r.is_anomaly:
            type_name = r.anomaly_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

    anomalies_count = sum(1 for r in results if r.is_anomaly)

    logger.info(
        "Test detection completed",
        total_points=len(request.values),
        anomalies=anomalies_count,
    )

    return {
        "total_points": len(request.values),
        "anomalies_detected": anomalies_count,
        "results": anomaly_items,
        "summary": type_counts,
    }


# ==================== Prediction Endpoints ====================


class PredictionPointResponse(BaseModel):
    """A single predicted data point with confidence interval."""
    timestamp: str
    value: float = Field(description="预测值 (yhat)")
    confidence: float = Field(description="预测置信度 (0-1)")
    value_lower: float = Field(description="置信区间下界 (yhat_lower)")
    value_upper: float = Field(description="置信区间上界 (yhat_upper)")


class PredictionResponse(BaseModel):
    """Response for prediction endpoint."""
    model_config = {"protected_namespaces": ()}

    device_id: str
    pollutant_code: str
    time_range: dict[str, str]
    historical_data: list[dict[str, Any]]
    predictions: list[PredictionPointResponse]
    model_type: str = Field(description="模型类型: prophet, simple_average, 或 insufficient_data")
    metrics: dict[str, Any]
    message: str | None = None


@router.get(
    "/predict/{device_id}",
    response_model=PredictionResponse,
    summary="预测污染物趋势",
    description="使用线性回归或加权移动平均预测未来污染物浓度趋势",
)
async def predict_device_trend(
    device_id: str,
    pollutant_code: str = Query(default="w01018", description="污染物代码 (默认: w01018/COD)"),
    hours: int = Query(default=24, ge=1, le=168, description="历史数据时间范围 (小时)"),
    prediction_hours: int = Query(default=4, ge=1, le=24, description="预测时间范围 (小时)"),
) -> dict[str, Any]:
    """Predict pollutant concentration trends for a device.

    Uses Linear Regression when sufficient data is available (>= 10 points),
    falls back to Weighted Moving Average for limited data.

    Returns:
    - historical_data: Simplified historical data points for charting
    - predictions: Future predicted values with timestamps and confidence
    - model_type: The model used for prediction
    - metrics: Model performance metrics (R² for LR, WMA value for WMA)
    """
    try:
        result = await predict_trend(
            device_id=device_id,
            pollutant_code=pollutant_code,
            hours=hours,
            prediction_hours=prediction_hours,
        )

        logger.info(
            "Prediction completed",
            device_id=device_id,
            pollutant_code=pollutant_code,
            model_type=result.get("model_type"),
            predictions=len(result.get("predictions", [])),
        )

        return result

    except Exception as e:
        logger.error("Prediction failed", device_id=device_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"预测失败: {str(e)}",
        )


# ==================== Mock Data Injection (Development Only) ====================


class InjectMockDataRequest(BaseModel):
    """Request body for mock data injection."""
    device_id: str = Field(default="BEIJING001", description="设备ID")
    pollutant_code: str = Field(default="w01018", description="污染物代码")
    days: int = Field(default=7, ge=1, le=30, description="历史数据天数 (默认7天)")
    interval_minutes: int = Field(default=1, ge=1, le=60, description="数据间隔 (分钟)")
    trend: str = Field(default="up", description="趋势方向: up, down, none")


def _generate_periodic_value(
    timestamp: datetime,
    pollutant_code: str,
    day_index: int = 0,
    total_days: int = 7,
    trend: str = "up",
) -> float:
    """Generate a value with daily periodicity, trend, and noise."""
    hour = timestamp.hour
    minute = timestamp.minute
    decimal_hour = hour + minute / 60.0

    # Define pollutant-specific ranges
    if pollutant_code == "w01018":  # COD
        day_min, day_max = 50.0, 85.0
        night_min, night_max = 15.0, 35.0
        noise_range = 5.0
    elif pollutant_code == "w21003":  # 氨氮
        day_min, day_max = 8.0, 18.0
        night_min, night_max = 2.0, 6.0
        noise_range = 1.5
    else:  # Default
        day_min, day_max = 40.0, 80.0
        night_min, night_max = 10.0, 30.0
        noise_range = 4.0

    # Calculate trend adjustment (±10% over the period)
    if trend == "up":
        trend_factor = 1.0 + (day_index / max(total_days, 1)) * 0.1
    elif trend == "down":
        trend_factor = 1.0 - (day_index / max(total_days, 1)) * 0.1
    else:
        trend_factor = 1.0

    # Daytime (8:00-20:00) or nighttime pattern
    if 8 <= hour < 20:
        phase = (decimal_hour - 8) / 12.0 * math.pi
        amplitude = (day_max - day_min) / 2.0
        midpoint = (day_max + day_min) / 2.0
        base_value = midpoint + amplitude * math.sin(phase)
    else:
        if hour >= 20:
            phase = (decimal_hour - 20) / 4.0 * math.pi / 2
            base_value = night_max - (night_max - night_min) * math.sin(phase)
        else:
            phase = decimal_hour / 8.0 * math.pi / 2
            base_value = night_min + (night_max - night_min) * math.sin(phase)

    # Apply trend
    base_value *= trend_factor

    # Add random noise (uniform for realistic spikes)
    noise = random.uniform(-noise_range, noise_range)
    return max(0.1, round(base_value + noise, 2))


@router.post(
    "/inject-mock-data",
    summary="注入测试数据 (仅Mock模式)",
    description="在Mock模式下注入具有日周期性规律的测试数据，用于测试NeuralProphet预测",
)
async def inject_mock_data(request: InjectMockDataRequest) -> dict[str, Any]:
    """Inject mock historical data with daily periodicity.

    This endpoint only works in mock mode (TDENGINE_MOCK=true).
    Data has sinusoidal daily patterns:
    - Daytime (8:00-20:00): Higher values with sine wave
    - Nighttime (20:00-8:00): Lower baseline values
    - Optional trend (up/down) over the period
    """
    client = get_tdengine_client()

    if not client.mock_mode:
        raise HTTPException(
            status_code=400,
            detail="此端点仅在Mock模式下可用 (设置 TDENGINE_MOCK=true)",
        )

    # Calculate time range (days instead of hours)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=request.days)

    # Generate all data points with batch insert for efficiency
    data_points = []
    current_time = start_time
    day_index = 0
    last_day = current_time.day

    while current_time <= end_time:
        # Track day changes for trend calculation
        if current_time.day != last_day:
            day_index += 1
            last_day = current_time.day

        value = _generate_periodic_value(
            current_time,
            request.pollutant_code,
            day_index=day_index,
            total_days=request.days,
            trend=request.trend,
        )
        data_points.append({
            "ts": current_time,
            "device_id": request.device_id,
            "pollutant_code": request.pollutant_code,
            "org_id": "default",
            "value": value,
            "flag": "N",
            "status": 0,
        })
        current_time += timedelta(minutes=request.interval_minutes)

    # Batch insert into mock storage for efficiency
    client._mock_data.extend(data_points)
    inserted = len(data_points)

    logger.info(
        "Mock data injected (batch)",
        device_id=request.device_id,
        pollutant_code=request.pollutant_code,
        data_points=inserted,
        days=request.days,
        trend=request.trend,
    )

    return {
        "success": True,
        "device_id": request.device_id,
        "pollutant_code": request.pollutant_code,
        "data_points_inserted": inserted,
        "time_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "trend": request.trend,
        "message": f"成功注入 {inserted} 个数据点 ({request.days} 天)",
    }


# ==================== AI Report Generation (SSE) ====================


def _get_spark_client() -> SparkClient:
    """获取 SparkClient 实例"""
    if not settings.spark_app_id or not settings.spark_api_key or not settings.spark_api_secret:
        raise HTTPException(
            status_code=500,
            detail="Spark API 未配置，请设置 SPARK_APP_ID, SPARK_API_KEY, SPARK_API_SECRET 环境变量",
        )

    return SparkClient(
        app_id=settings.spark_app_id,
        api_secret=settings.spark_api_secret,
        api_key=settings.spark_api_key,
        spark_url=settings.spark_api_url,
        domain=settings.spark_domain,
    )


async def _generate_report_stream(
    device_id: str,
    device_name: str,
    pollutant_code: str | None,
    target_date: date,
) -> AsyncGenerator[str, None]:
    """
    生成 AI 诊断报告的 SSE 数据流

    Args:
        device_id: 设备 ID
        device_name: 设备名称
        pollutant_code: 污染物代码（None 表示综合分析所有污染物）
        target_date: 目标日期

    Yields:
        SSE 格式的数据块
    """
    try:
        # 步骤1：发送开始事件
        is_comprehensive = pollutant_code is None
        mode_desc = "综合分析" if is_comprehensive else f"分析 {pollutant_code}"
        yield f"event: start\ndata: {json.dumps({'status': 'analyzing', 'message': f'正在{mode_desc}数据...', 'mode': 'comprehensive' if is_comprehensive else 'single'})}\n\n"

        # 步骤2：获取数据统计特征
        logger.info(
            "Fetching device stats",
            device_id=device_id,
            date=target_date.isoformat(),
            comprehensive=is_comprehensive,
        )
        stats = await analyze_device_daily_stats(
            device_id=device_id,
            target_date=target_date,
            pollutant_code=pollutant_code,  # None = 查询所有污染物
        )

        if not stats.get("pollutants"):
            yield f"event: error\ndata: {json.dumps({'error': f'设备 {device_id} 在 {target_date} 无监测数据'})}\n\n"
            return

        pollutant_count = len(stats["pollutants"])
        yield f"event: progress\ndata: {json.dumps({'status': 'data_ready', 'message': f'数据分析完成，共 {pollutant_count} 种污染物，正在生成报告...', 'pollutant_count': pollutant_count})}\n\n"

        # 步骤3：根据模式构建 Prompt
        if is_comprehensive:
            # 综合分析模式：分析所有污染物
            # 确定领域（从第一个污染物推断）
            first_code = stats["pollutants"][0]["pollutant_code"]
            domain = get_domain_from_pollutant_code(first_code)

            prompt = build_comprehensive_diagnosis_prompt(
                device_id=device_id,
                device_name=device_name,
                report_date=target_date.isoformat(),
                pollutants_stats=stats["pollutants"],
                total_data_points=stats.get("data_count", 0),
                domain=domain,
            )
            logger.info(
                "Built comprehensive prompt",
                pollutant_count=pollutant_count,
                prompt_length=len(prompt),
            )
        else:
            # 单污染物分析模式（保持兼容）
            pollutant_stats = stats["pollutants"][0]
            p_code = pollutant_stats["pollutant_code"]

            domain = get_domain_from_pollutant_code(p_code)
            knowledge = get_domain_knowledge(domain)
            pollutant_info = get_pollutant_info(domain, p_code)
            p_name = pollutant_info.get("name", p_code)
            unit = pollutant_info.get("unit", "")

            over_limit_count = pollutant_stats.get("over_limit_count", 0)
            threshold = pollutant_stats.get("threshold_value")

            if over_limit_count > 0:
                compliance_status = f"存在 {over_limit_count} 次超标"
            elif threshold and pollutant_stats["avg_val"] > threshold * 0.9:
                compliance_status = "临近阈值，需关注"
            else:
                compliance_status = "正常达标"

            prompt = build_expert_diagnosis_prompt(
                device_type=domain,
                device_name=device_name,
                pollutant_code=p_code,
                pollutant_name=p_name,
                report_date=target_date.isoformat(),
                avg_val=pollutant_stats["avg_val"],
                max_val=pollutant_stats["max_val"],
                min_val=pollutant_stats["min_val"],
                peak_time=pollutant_stats.get("peak_time", "未知"),
                alarm_count=over_limit_count,
                compliance_status=compliance_status,
                trend_desc=pollutant_stats.get("trend_description", "数据正常"),
                unit=unit,
            )

        logger.debug("Prompt built", prompt_length=len(prompt))

        # 步骤4：调用 Spark 大模型
        spark_client = _get_spark_client()
        messages = [{"role": "user", "content": prompt}]

        yield f"event: progress\ndata: {json.dumps({'status': 'generating', 'message': 'AI 正在生成诊断报告...'})}\n\n"

        # 步骤5：流式输出 AI 响应
        async for chunk in spark_client.chat_stream(messages):
            yield f"event: content\ndata: {json.dumps({'content': chunk})}\n\n"
            await asyncio.sleep(0.01)

        # 步骤6：发送完成事件
        yield f"event: done\ndata: {json.dumps({'status': 'completed', 'stats': stats, 'mode': 'comprehensive' if is_comprehensive else 'single'})}\n\n"

    except SparkClientError as e:
        logger.error("Spark API error", error=str(e))
        yield f"event: error\ndata: {json.dumps({'error': f'AI 服务错误: {str(e)}'})}\n\n"

    except Exception as e:
        logger.error("Report generation failed", error=str(e))
        yield f"event: error\ndata: {json.dumps({'error': f'生成报告失败: {str(e)}'})}\n\n"


@router.get(
    "/report/stream",
    summary="流式生成 AI 诊断报告 (SSE)",
    description="""
使用 Server-Sent Events (SSE) 流式返回 AI 生成的智能运维诊断报告。

**分析模式**:
- **综合分析**（默认）: 不传 pollutant 参数，分析设备当日所有污染物数据
- **单因子分析**: 传入 pollutant 参数，仅分析指定污染物

**事件类型**:
- `start`: 开始分析，包含 mode 字段（comprehensive/single）
- `progress`: 进度更新，包含 pollutant_count
- `content`: AI 生成的内容片段
- `done`: 完成，包含统计数据
- `error`: 错误信息

**前端使用示例**:
```javascript
// 综合分析（推荐）
const evtSource = new EventSource('/api/v1/ai/report/stream?device_id=DEV001');

// 单因子分析
const evtSource = new EventSource('/api/v1/ai/report/stream?device_id=DEV001&pollutant=w01018');

evtSource.addEventListener('content', (e) => {
    const data = JSON.parse(e.data);
    document.getElementById('report').innerHTML += data.content;
});
```
""",
    responses={
        200: {
            "description": "SSE 事件流",
            "content": {"text/event-stream": {}},
        },
    },
)
async def stream_ai_report(
    device_id: str = Query(..., description="设备 ID 或 MN 号"),
    device_name: str = Query(default="监测设备", description="设备名称（用于报告显示）"),
    pollutant: str | None = Query(default=None, description="污染物代码，不传则综合分析所有污染物"),
    report_date: str | None = Query(default=None, description="报告日期 (YYYY-MM-DD)，默认为今天"),
) -> StreamingResponse:
    """
    流式生成 AI 诊断报告

    全链路流程：
    1. 从 TDengine 查询设备监测数据
    2. 使用 pandas 计算统计特征
    3. 根据污染物代码确定领域知识
    4. 动态组装专业 Prompt
    5. 调用星火大模型生成报告
    6. 通过 SSE 流式返回
    """
    # 解析日期
    if report_date:
        try:
            target_date = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    else:
        target_date = date.today()

    logger.info(
        "Starting AI report stream",
        device_id=device_id,
        pollutant=pollutant,
        date=target_date.isoformat(),
    )

    return StreamingResponse(
        _generate_report_stream(
            device_id=device_id,
            device_name=device_name,
            pollutant_code=pollutant,
            target_date=target_date,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@router.get(
    "/report/sync",
    summary="同步生成 AI 诊断报告",
    description="""
非流式版本，等待完整报告生成后一次性返回。

**分析模式**:
- **综合分析**（默认）: 不传 pollutant 参数，分析设备当日所有污染物数据
- **单因子分析**: 传入 pollutant 参数，仅分析指定污染物
""",
)
async def generate_ai_report_sync(
    device_id: str = Query(..., description="设备 ID"),
    device_name: str = Query(default="监测设备", description="设备名称"),
    pollutant: str | None = Query(default=None, description="污染物代码，不传则综合分析所有污染物"),
    report_date: str | None = Query(default=None, description="报告日期 (YYYY-MM-DD)"),
) -> dict[str, Any]:
    """
    同步生成 AI 诊断报告（非流式）

    适用于不支持 SSE 的客户端
    """
    # 解析日期
    if report_date:
        try:
            target_date = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    else:
        target_date = date.today()

    is_comprehensive = pollutant is None
    logger.info(
        "Generating AI report (sync)",
        device_id=device_id,
        pollutant=pollutant,
        comprehensive=is_comprehensive,
        date=target_date.isoformat(),
    )

    # 获取数据统计（pollutant=None 表示获取所有污染物）
    stats = await analyze_device_daily_stats(
        device_id=device_id,
        target_date=target_date,
        pollutant_code=pollutant,
    )

    if not stats.get("pollutants"):
        raise HTTPException(
            status_code=404,
            detail=f"设备 {device_id} 在 {target_date} 无监测数据",
        )

    # 根据模式构建 Prompt
    if is_comprehensive:
        # 综合分析模式
        first_code = stats["pollutants"][0]["pollutant_code"]
        domain = get_domain_from_pollutant_code(first_code)

        prompt = build_comprehensive_diagnosis_prompt(
            device_id=device_id,
            device_name=device_name,
            report_date=target_date.isoformat(),
            pollutants_stats=stats["pollutants"],
            total_data_points=stats.get("data_count", 0),
            domain=domain,
        )

        # 调用 AI
        try:
            spark_client = _get_spark_client()
            messages = [{"role": "user", "content": prompt}]
            report_content = await spark_client.chat(messages)
        except SparkClientError as e:
            raise HTTPException(status_code=500, detail=f"AI 服务错误: {str(e)}")

        return {
            "device_id": device_id,
            "device_name": device_name,
            "mode": "comprehensive",
            "pollutant_count": len(stats["pollutants"]),
            "report_date": target_date.isoformat(),
            "domain": domain,
            "stats": stats,
            "report": report_content,
        }
    else:
        # 单污染物分析模式
        pollutant_stats = stats["pollutants"][0]
        p_code = pollutant_stats["pollutant_code"]

        domain = get_domain_from_pollutant_code(p_code)
        knowledge = get_domain_knowledge(domain)
        pollutant_info = get_pollutant_info(domain, p_code)
        p_name = pollutant_info.get("name", p_code)
        unit = pollutant_info.get("unit", "")

        over_limit_count = pollutant_stats.get("over_limit_count", 0)
        threshold = pollutant_stats.get("threshold_value")

        if over_limit_count > 0:
            compliance_status = f"存在 {over_limit_count} 次超标"
        elif threshold and pollutant_stats["avg_val"] > threshold * 0.9:
            compliance_status = "临近阈值，需关注"
        else:
            compliance_status = "正常达标"

        prompt = build_expert_diagnosis_prompt(
            device_type=domain,
            device_name=device_name,
            pollutant_code=p_code,
            pollutant_name=p_name,
            report_date=target_date.isoformat(),
            avg_val=pollutant_stats["avg_val"],
            max_val=pollutant_stats["max_val"],
            min_val=pollutant_stats["min_val"],
            peak_time=pollutant_stats.get("peak_time", "未知"),
            alarm_count=over_limit_count,
            compliance_status=compliance_status,
            trend_desc=pollutant_stats.get("trend_description", "数据正常"),
            unit=unit,
        )

        # 调用 AI
        try:
            spark_client = _get_spark_client()
            messages = [{"role": "user", "content": prompt}]
            report_content = await spark_client.chat(messages)
        except SparkClientError as e:
            raise HTTPException(status_code=500, detail=f"AI 服务错误: {str(e)}")

        return {
            "device_id": device_id,
            "device_name": device_name,
            "mode": "single",
            "pollutant_code": p_code,
            "pollutant_name": p_name,
            "report_date": target_date.isoformat(),
            "domain": domain,
            "stats": stats,
            "report": report_content,
        }
