#!/usr/bin/env python3
"""
AI 报告 SSE 流式接口测试脚本

测试从数据查询到 AI 生成的全链路流程

用法:
    # 方式1: 直接运行（需要后端服务已启动）
    python scripts/test_ai_stream.py

    # 方式2: 使用 Mock 模式测试（无需真实 TDengine）
    TDENGINE_MOCK=true python scripts/test_ai_stream.py --mock

环境变量:
    SPARK_APP_ID: 讯飞 APPID
    SPARK_API_KEY: API Key
    SPARK_API_SECRET: API Secret
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_sse_via_http():
    """通过 HTTP 客户端测试 SSE 接口"""
    import httpx

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    device_id = os.getenv("TEST_DEVICE_ID", "TESTDEV001")

    url = f"{base_url}/api/v1/ai/report/stream"
    params = {
        "device_id": device_id,
        "device_name": "测试污水处理设备",
        "pollutant": "w01018",
    }

    print(f"\n{'=' * 60}")
    print("SSE 流式接口测试 (HTTP 客户端)")
    print(f"{'=' * 60}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"{'=' * 60}\n")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("GET", url, params=params) as response:
                if response.status_code != 200:
                    print(f"错误: HTTP {response.status_code}")
                    content = await response.aread()
                    print(content.decode())
                    return

                print("开始接收 SSE 事件...\n")

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk

                    # 解析 SSE 事件
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)

                        event_type = "message"
                        event_data = ""

                        for line in event_str.split("\n"):
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:"):
                                event_data = line[5:].strip()

                        if event_data:
                            try:
                                data = json.loads(event_data)

                                if event_type == "start":
                                    print(f"[开始] {data.get('message', '')}")
                                elif event_type == "progress":
                                    print(f"[进度] {data.get('message', '')}")
                                elif event_type == "content":
                                    # 打字机效果输出
                                    print(data.get("content", ""), end="", flush=True)
                                elif event_type == "done":
                                    print(f"\n\n[完成] 报告生成成功")
                                    stats = data.get("stats", {})
                                    if stats:
                                        print(f"数据点数: {stats.get('data_count', 0)}")
                                elif event_type == "error":
                                    print(f"\n[错误] {data.get('error', '')}")

                            except json.JSONDecodeError:
                                print(f"[原始] {event_data}")

    except httpx.ConnectError:
        print("错误: 无法连接到后端服务")
        print("请确保后端已启动: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"错误: {e}")


async def test_direct_generation():
    """直接测试 AI 报告生成（不通过 HTTP）"""
    from app.db.tdengine_client import get_tdengine_client
    from app.services.data_analysis_service import analyze_device_daily_stats
    from app.services.llm.spark_client import SparkClient
    from app.core.prompts import (
        build_expert_diagnosis_prompt,
        get_domain_from_pollutant_code,
        get_pollutant_info,
    )

    print(f"\n{'=' * 60}")
    print("直接测试 AI 报告生成")
    print(f"{'=' * 60}\n")

    # 初始化 TDengine 客户端
    client = get_tdengine_client()
    await client.connect()

    device_id = "TESTDEV001"
    pollutant_code = "w01018"
    target_date = date.today()

    # 如果是 Mock 模式，注入测试数据
    if client.mock_mode:
        print("[Mock 模式] 注入测试数据...")
        base_time = datetime.combine(target_date, datetime.min.time())

        for i in range(0, 1440, 5):  # 每5分钟一条
            ts = base_time + timedelta(minutes=i)
            hour = ts.hour

            # 模拟日间波动
            if 14 <= hour <= 18:
                value = 60 + random.uniform(-10, 30)
            elif 6 <= hour < 14:
                value = 40 + random.uniform(-10, 15)
            else:
                value = 25 + random.uniform(-5, 10)

            await client.insert_monitoring_data(
                device_id=device_id,
                pollutant_code=pollutant_code,
                org_id="ORG001",
                timestamp=ts,
                value=value,
                flag="N",
                status=0,
            )

        print(f"[Mock 模式] 注入 {len(client._mock_data)} 条数据\n")

    # 步骤1：获取数据统计
    print("步骤 1: 获取数据统计...")
    stats = await analyze_device_daily_stats(
        device_id=device_id,
        target_date=target_date,
        pollutant_code=pollutant_code,
    )

    if not stats.get("pollutants"):
        print(f"错误: 设备 {device_id} 无数据")
        return

    pollutant_stats = stats["pollutants"][0]
    print(f"  平均值: {pollutant_stats['avg_val']}")
    print(f"  最大值: {pollutant_stats['max_val']} (于 {pollutant_stats.get('peak_time', '未知')})")
    print(f"  最小值: {pollutant_stats['min_val']}")
    print(f"  波动率: {pollutant_stats['volatility']}%")
    print(f"  趋势: {pollutant_stats.get('trend_description', '未知')}\n")

    # 步骤2：构建 Prompt
    print("步骤 2: 构建 Prompt...")
    domain = get_domain_from_pollutant_code(pollutant_code)
    pollutant_info = get_pollutant_info(domain, pollutant_code)

    prompt = build_expert_diagnosis_prompt(
        device_type=domain,
        device_name="测试污水处理设备",
        pollutant_code=pollutant_code,
        pollutant_name=pollutant_info.get("name", pollutant_code),
        report_date=target_date.isoformat(),
        avg_val=pollutant_stats["avg_val"],
        max_val=pollutant_stats["max_val"],
        min_val=pollutant_stats["min_val"],
        peak_time=pollutant_stats.get("peak_time", "未知"),
        alarm_count=pollutant_stats.get("over_limit_count", 0),
        compliance_status="正常达标",
        trend_desc=pollutant_stats.get("trend_description", "数据正常"),
        unit=pollutant_info.get("unit", "mg/L"),
    )

    print(f"  Prompt 长度: {len(prompt)} 字符\n")

    # 步骤3：调用 Spark AI
    print("步骤 3: 调用 Spark AI 生成报告...")

    # 从环境变量获取配置
    app_id = os.getenv("SPARK_APP_ID", "")
    api_key = os.getenv("SPARK_API_KEY", "")
    api_secret = os.getenv("SPARK_API_SECRET", "")

    if not all([app_id, api_key, api_secret]):
        print("\n警告: 未配置 Spark API 凭证")
        print("请设置以下环境变量:")
        print("  export SPARK_APP_ID=your_app_id")
        print("  export SPARK_API_KEY=your_api_key")
        print("  export SPARK_API_SECRET=your_api_secret")
        print("\n仅展示 Prompt 预览:")
        print("-" * 40)
        print(prompt[:500])
        print("...")
        return

    spark_client = SparkClient(
        app_id=app_id,
        api_secret=api_secret,
        api_key=api_key,
    )

    print("\nAI 报告输出 (打字机效果):")
    print("-" * 40)

    messages = [{"role": "user", "content": prompt}]

    async for chunk in spark_client.chat_stream(messages):
        print(chunk, end="", flush=True)

    print("\n" + "-" * 40)
    print("\n报告生成完成!")


async def test_curl_command():
    """输出 curl 测试命令"""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

    print(f"\n{'=' * 60}")
    print("使用 curl 测试 SSE 接口")
    print(f"{'=' * 60}\n")

    cmd = f'''curl -N "{base_url}/api/v1/ai/report/stream?device_id=TESTDEV001&device_name=测试设备&pollutant=w01018"'''

    print("命令:")
    print(cmd)
    print("\n说明: -N 参数禁用缓冲，实现实时输出")


def main():
    parser = argparse.ArgumentParser(description="AI 报告 SSE 流式接口测试")
    parser.add_argument(
        "--mode",
        choices=["http", "direct", "curl"],
        default="http",
        help="测试模式: http=通过HTTP测试, direct=直接测试, curl=输出curl命令",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="使用 Mock 模式（自动注入测试数据）",
    )

    args = parser.parse_args()

    if args.mock:
        os.environ["TDENGINE_MOCK"] = "true"

    print(f"\n{'#' * 60}")
    print("# EcoMind AI 报告流式接口测试")
    print(f"{'#' * 60}")
    print(f"测试模式: {args.mode}")
    print(f"Mock 模式: {'是' if args.mock else '否'}")

    if args.mode == "http":
        asyncio.run(test_sse_via_http())
    elif args.mode == "direct":
        asyncio.run(test_direct_generation())
    elif args.mode == "curl":
        asyncio.run(test_curl_command())


if __name__ == "__main__":
    main()
