#!/usr/bin/env python3
"""
实时监测数据演示脚本
模拟数采仪上报包含常用指标、重金属、异常数据的监测数据

用法:
    python scripts/demo_realtime_monitoring.py [--device DEVICE_MN] [--interval SECONDS]
"""

import asyncio
import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.tdengine_client import TDengineClient


# 模拟数据配置
POLLUTANT_PROFILES = {
    # 常用指标 - 污水处理厂典型值
    "common": {
        "w01018": {"name": "COD", "base": 45, "std": 15, "unit": "mg/L", "limit": 60},  # 一级A标准
        "w21003": {"name": "氨氮", "base": 3.5, "std": 1.5, "unit": "mg/L", "limit": 8},
        "w01001": {"name": "pH", "base": 7.2, "std": 0.3, "unit": "", "limit_low": 6, "limit_high": 9},
        "w21011": {"name": "总磷", "base": 0.4, "std": 0.15, "unit": "mg/L", "limit": 1},
        "w21001": {"name": "总氮", "base": 12, "std": 4, "unit": "mg/L", "limit": 20},
        "w01009": {"name": "溶解氧", "base": 6.5, "std": 1.5, "unit": "mg/L", "limit_low": 2},
    },
    # 一类重金属 - 电镀废水
    "heavy_metals_class1": {
        "w20111": {"name": "总汞", "base": 0.00008, "std": 0.00003, "unit": "mg/L", "limit": 0.001},
        "w20115": {"name": "总镉", "base": 0.008, "std": 0.003, "unit": "mg/L", "limit": 0.01},
        "w20117": {"name": "六价铬", "base": 0.03, "std": 0.015, "unit": "mg/L", "limit": 0.05},
        "w20119": {"name": "总砷", "base": 0.02, "std": 0.01, "unit": "mg/L", "limit": 0.1},
        "w20120": {"name": "总铅", "base": 0.05, "std": 0.02, "unit": "mg/L", "limit": 0.1},
    },
    # 二类重金属 - 电镀废水
    "heavy_metals_class2": {
        "w20121": {"name": "总镍", "base": 0.3, "std": 0.15, "unit": "mg/L", "limit": 0.5},
        "w20122": {"name": "总铜", "base": 0.25, "std": 0.1, "unit": "mg/L", "limit": 0.5},
        "w20123": {"name": "总锌", "base": 0.8, "std": 0.3, "unit": "mg/L", "limit": 1.5},
        "w20116": {"name": "总铬", "base": 0.6, "std": 0.25, "unit": "mg/L", "limit": 1.0},
        "w20124": {"name": "总锰", "base": 0.5, "std": 0.2, "unit": "mg/L", "limit": 2.0},
    },
    # 电镀特征污染物
    "electroplating": {
        "w21016": {"name": "氰化物", "base": 0.15, "std": 0.08, "unit": "mg/L", "limit": 0.3},
    }
}

# 异常场景配置
ANOMALY_SCENARIOS = [
    {
        "name": "COD超标",
        "pollutant": "w01018",
        "value": 85,  # 超过60mg/L限值
        "flag": "B",  # 超标标记
    },
    {
        "name": "氨氮超标",
        "pollutant": "w21003",
        "value": 12,  # 超过8mg/L限值
        "flag": "B",
    },
    {
        "name": "六价铬超标",
        "pollutant": "w20117",
        "value": 0.08,  # 超过0.05mg/L限值
        "flag": "B",
    },
    {
        "name": "总镍超标",
        "pollutant": "w20121",
        "value": 0.65,  # 超过0.5mg/L限值
        "flag": "B",
    },
]


def generate_value(config: dict, add_trend: float = 0, anomaly_prob: float = 0.05) -> tuple[float, str]:
    """
    生成模拟监测值

    Args:
        config: 污染物配置
        add_trend: 趋势偏移量
        anomaly_prob: 异常概率

    Returns:
        (value, flag)
    """
    base = config["base"]
    std = config["std"]

    # 随机波动
    value = base + random.gauss(0, std) + add_trend

    # 确保非负
    value = max(0, value)

    # 判断是否超标
    flag = "N"  # 正常

    if "limit" in config and value > config["limit"]:
        flag = "B"  # 超标
    elif "limit_low" in config and value < config["limit_low"]:
        flag = "B"
    elif "limit_high" in config and value > config["limit_high"]:
        flag = "B"

    # 随机触发异常（模拟设备故障等）
    if random.random() < anomaly_prob:
        flag = "D"  # 设备故障

    return round(value, 6), flag


async def generate_historical_data(
    client: TDengineClient,
    device_id: str,
    org_id: str,
    hours: int = 24,
    interval_minutes: int = 15,
    include_anomaly: bool = True,
):
    """
    生成历史数据（用于AI预测训练）
    """
    print(f"\n{'='*60}")
    print(f"生成 {hours} 小时历史数据 (间隔 {interval_minutes} 分钟)")
    print(f"设备: {device_id}")
    print(f"{'='*60}\n")

    now = datetime.now()
    start_time = now - timedelta(hours=hours)

    # 计算数据点数量
    total_points = (hours * 60) // interval_minutes

    # 模拟趋势：COD在某个时段升高
    trend_start = total_points // 3
    trend_end = trend_start + total_points // 4

    data_count = 0
    anomaly_count = 0

    for i in range(total_points):
        timestamp = start_time + timedelta(minutes=i * interval_minutes)

        # 计算趋势偏移
        if trend_start <= i <= trend_end:
            # 趋势期间，COD逐渐升高
            progress = (i - trend_start) / (trend_end - trend_start)
            cod_trend = 20 * progress  # 最高升高20
        elif i > trend_end:
            # 趋势结束后，逐渐恢复
            recovery = min(1, (i - trend_end) / (total_points // 4))
            cod_trend = 20 * (1 - recovery)
        else:
            cod_trend = 0

        pollutants = {}

        # 生成常用指标
        for code, config in POLLUTANT_PROFILES["common"].items():
            trend = cod_trend if code == "w01018" else 0
            value, flag = generate_value(config, add_trend=trend)
            pollutants[code] = {"value": value, "flag": flag}

        # 生成一类重金属
        for code, config in POLLUTANT_PROFILES["heavy_metals_class1"].items():
            value, flag = generate_value(config)
            pollutants[code] = {"value": value, "flag": flag}

        # 生成二类重金属
        for code, config in POLLUTANT_PROFILES["heavy_metals_class2"].items():
            value, flag = generate_value(config)
            pollutants[code] = {"value": value, "flag": flag}

        # 生成电镀特征污染物
        for code, config in POLLUTANT_PROFILES["electroplating"].items():
            value, flag = generate_value(config)
            pollutants[code] = {"value": value, "flag": flag}

        # 随机插入异常场景
        if include_anomaly and random.random() < 0.08:  # 8%概率出现异常
            scenario = random.choice(ANOMALY_SCENARIOS)
            pollutants[scenario["pollutant"]] = {
                "value": scenario["value"] * random.uniform(0.9, 1.2),
                "flag": scenario["flag"]
            }
            anomaly_count += 1

        # 写入宽表
        success = await client.insert_wide_monitoring_data(
            device_id=device_id,
            org_id=org_id,
            timestamp=timestamp,
            pollutants=pollutants,
            data_type="minute"
        )

        # 同时写入窄表（用于现有查询兼容）
        for code, data in pollutants.items():
            await client.insert_monitoring_data(
                device_id=device_id,
                org_id=org_id,
                pollutant_code=code,
                value=data["value"],
                flag=data["flag"],
                timestamp=timestamp
            )

        if success:
            data_count += 1

        # 进度显示
        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{total_points} ({100*(i+1)//total_points}%)")

    print(f"\n✅ 历史数据生成完成!")
    print(f"   - 总数据点: {data_count}")
    print(f"   - 异常数据点: {anomaly_count}")
    print(f"   - 污染物种类: {len(POLLUTANT_PROFILES['common']) + len(POLLUTANT_PROFILES['heavy_metals_class1']) + len(POLLUTANT_PROFILES['heavy_metals_class2']) + len(POLLUTANT_PROFILES['electroplating'])}")


async def generate_realtime_data(
    client: TDengineClient,
    device_id: str,
    org_id: str,
    interval_seconds: int = 60,
    duration_minutes: int = 10,
    include_anomaly: bool = True,
):
    """
    生成实时数据流（模拟数采仪持续上报）
    """
    print(f"\n{'='*60}")
    print(f"开始实时数据模拟 (间隔 {interval_seconds} 秒, 持续 {duration_minutes} 分钟)")
    print(f"设备: {device_id}")
    print(f"{'='*60}\n")

    total_iterations = (duration_minutes * 60) // interval_seconds

    for i in range(total_iterations):
        timestamp = datetime.now()

        pollutants = {}
        anomalies = []

        # 生成所有指标
        all_profiles = {
            **POLLUTANT_PROFILES["common"],
            **POLLUTANT_PROFILES["heavy_metals_class1"],
            **POLLUTANT_PROFILES["heavy_metals_class2"],
            **POLLUTANT_PROFILES["electroplating"],
        }

        for code, config in all_profiles.items():
            value, flag = generate_value(config)
            pollutants[code] = {"value": value, "flag": flag}

            if flag != "N":
                anomalies.append(f"{config['name']}({code}): {value:.4f} [{flag}]")

        # 随机触发异常
        if include_anomaly and random.random() < 0.15:
            scenario = random.choice(ANOMALY_SCENARIOS)
            pollutants[scenario["pollutant"]] = {
                "value": scenario["value"] * random.uniform(0.95, 1.15),
                "flag": scenario["flag"]
            }
            config = all_profiles.get(scenario["pollutant"], {})
            anomalies.append(f"⚠️ {scenario['name']}: {pollutants[scenario['pollutant']]['value']:.4f}")

        # 写入数据
        await client.insert_wide_monitoring_data(
            device_id=device_id,
            org_id=org_id,
            timestamp=timestamp,
            pollutants=pollutants,
            data_type="realtime"
        )

        for code, data in pollutants.items():
            await client.insert_monitoring_data(
                device_id=device_id,
                org_id=org_id,
                pollutant_code=code,
                value=data["value"],
                flag=data["flag"],
                timestamp=timestamp
            )

        # 打印状态
        print(f"[{timestamp.strftime('%H:%M:%S')}] 数据上报 #{i+1}/{total_iterations}")
        print(f"  常用: COD={pollutants['w01018']['value']:.2f}, 氨氮={pollutants['w21003']['value']:.3f}, pH={pollutants['w01001']['value']:.2f}")
        print(f"  重金属: Ni={pollutants['w20121']['value']:.4f}, Cu={pollutants['w20122']['value']:.4f}, Cr6+={pollutants['w20117']['value']:.4f}")

        if anomalies:
            print(f"  异常: {', '.join(anomalies)}")

        print()

        if i < total_iterations - 1:
            await asyncio.sleep(interval_seconds)

    print("✅ 实时数据模拟完成!")


async def main():
    parser = argparse.ArgumentParser(description="实时监测数据演示脚本")
    parser.add_argument("--device", default="BEIJING001", help="设备MN号")
    parser.add_argument("--org", default="00000000-0000-0000-0000-000000000001", help="组织ID")
    parser.add_argument("--historical-hours", type=int, default=24, help="历史数据小时数")
    parser.add_argument("--realtime-minutes", type=int, default=5, help="实时模拟分钟数")
    parser.add_argument("--interval", type=int, default=30, help="实时数据间隔(秒)")
    parser.add_argument("--no-anomaly", action="store_true", help="不生成异常数据")
    parser.add_argument("--historical-only", action="store_true", help="只生成历史数据")
    parser.add_argument("--realtime-only", action="store_true", help="只生成实时数据")

    args = parser.parse_args()

    print("\n" + "="*60)
    print("    EcoMind-AI 实时监测数据演示")
    print("="*60)
    print(f"\n配置:")
    print(f"  设备MN: {args.device}")
    print(f"  组织ID: {args.org}")
    print(f"  历史数据: {args.historical_hours} 小时")
    print(f"  实时模拟: {args.realtime_minutes} 分钟 (间隔 {args.interval} 秒)")
    print(f"  包含异常: {'否' if args.no_anomaly else '是'}")

    print("\n污染物配置:")
    print(f"  常用指标: {len(POLLUTANT_PROFILES['common'])} 种")
    print(f"  一类重金属: {len(POLLUTANT_PROFILES['heavy_metals_class1'])} 种")
    print(f"  二类重金属: {len(POLLUTANT_PROFILES['heavy_metals_class2'])} 种")
    print(f"  电镀特征: {len(POLLUTANT_PROFILES['electroplating'])} 种")

    # 初始化 TDengine 客户端
    client = TDengineClient()
    await client.connect()

    try:
        include_anomaly = not args.no_anomaly

        # 生成历史数据
        if not args.realtime_only:
            await generate_historical_data(
                client=client,
                device_id=args.device,
                org_id=args.org,
                hours=args.historical_hours,
                interval_minutes=15,
                include_anomaly=include_anomaly,
            )

        # 生成实时数据
        if not args.historical_only:
            await generate_realtime_data(
                client=client,
                device_id=args.device,
                org_id=args.org,
                interval_seconds=args.interval,
                duration_minutes=args.realtime_minutes,
                include_anomaly=include_anomaly,
            )

        print("\n" + "="*60)
        print("演示完成! 请刷新 Dashboard 查看效果:")
        print("  - 实时监测数据卡片")
        print("  - 趋势图 + AI预测")
        print("  - AI智能诊断")
        print("="*60 + "\n")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
