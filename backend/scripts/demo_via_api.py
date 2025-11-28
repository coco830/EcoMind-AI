#!/usr/bin/env python3
"""
通过 API 发送演示数据
直接向运行中的后端发送监测数据
"""

import asyncio
import aiohttp
import random
from datetime import datetime, timedelta
import sys

# API 配置
BASE_URL = "http://localhost:8000"
DEVICE_ID = "BEIJING001"

# 污染物配置
POLLUTANT_PROFILES = {
    # 常用指标
    "w01018": {"name": "COD", "base": 45, "std": 12, "limit": 60},
    "w21003": {"name": "氨氮", "base": 3.5, "std": 1.2, "limit": 8},
    "w01001": {"name": "pH", "base": 7.2, "std": 0.25},
    "w21011": {"name": "总磷", "base": 0.4, "std": 0.12, "limit": 1},
    "w21001": {"name": "总氮", "base": 12, "std": 3, "limit": 20},
    "w01009": {"name": "溶解氧", "base": 6.5, "std": 1.2},
    # 一类重金属
    "w20111": {"name": "总汞", "base": 0.00008, "std": 0.00002, "limit": 0.001},
    "w20115": {"name": "总镉", "base": 0.008, "std": 0.002, "limit": 0.01},
    "w20117": {"name": "六价铬", "base": 0.03, "std": 0.01, "limit": 0.05},
    "w20119": {"name": "总砷", "base": 0.02, "std": 0.008, "limit": 0.1},
    "w20120": {"name": "总铅", "base": 0.05, "std": 0.015, "limit": 0.1},
    # 二类重金属
    "w20121": {"name": "总镍", "base": 0.3, "std": 0.1, "limit": 0.5},
    "w20122": {"name": "总铜", "base": 0.25, "std": 0.08, "limit": 0.5},
    "w20123": {"name": "总锌", "base": 0.8, "std": 0.2, "limit": 1.5},
    "w20116": {"name": "总铬", "base": 0.6, "std": 0.2, "limit": 1.0},
    "w20124": {"name": "总锰", "base": 0.5, "std": 0.15, "limit": 2.0},
    # 电镀特征
    "w21016": {"name": "氰化物", "base": 0.15, "std": 0.06, "limit": 0.3},
}

# 异常场景
ANOMALY_SCENARIOS = [
    {"pollutant": "w01018", "value": 78, "name": "COD超标"},
    {"pollutant": "w21003", "value": 11, "name": "氨氮超标"},
    {"pollutant": "w20117", "value": 0.065, "name": "六价铬超标"},
    {"pollutant": "w20121", "value": 0.58, "name": "总镍超标"},
]


def generate_value(config: dict, trend: float = 0) -> tuple[float, str]:
    """生成监测值"""
    value = config["base"] + random.gauss(0, config["std"]) + trend
    value = max(0, value)
    flag = "N"
    if "limit" in config and value > config["limit"]:
        flag = "B"
    return round(value, 6), flag


async def login(session: aiohttp.ClientSession) -> str:
    """登录获取token"""
    async with session.post(f"{BASE_URL}/api/v1/auth/login", data={
        "username": "admin",
        "password": "admin123"
    }) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["access_token"]
        else:
            print(f"登录失败: {resp.status}")
            return ""


async def submit_data(session: aiohttp.ClientSession, token: str, data_points: list):
    """通过内部API提交数据（模拟TCP网关写入）"""
    headers = {"Authorization": f"Bearer {token}"}

    # 直接调用数据查询API来验证连接
    async with session.get(
        f"{BASE_URL}/api/v1/dashboard/stats",
        headers=headers
    ) as resp:
        if resp.status != 200:
            print(f"API连接失败: {resp.status}")
            return False

    return True


async def generate_and_display_data():
    """生成数据并显示（用于演示）"""
    print("\n" + "="*70)
    print("    EcoMind-AI 实时监测数据演示")
    print("="*70)

    print("\n正在生成演示数据...\n")

    # 生成24小时历史数据 + 趋势
    now = datetime.now()
    data_points = []

    # 趋势参数：COD在某段时间升高
    trend_start = 32  # 第32个点开始
    trend_peak = 48   # 第48个点达到峰值
    trend_end = 64    # 第64个点恢复

    total_points = 96  # 24小时，每15分钟一个点

    for i in range(total_points):
        timestamp = now - timedelta(minutes=(total_points - i - 1) * 15)

        # COD趋势
        if trend_start <= i < trend_peak:
            progress = (i - trend_start) / (trend_peak - trend_start)
            cod_trend = 25 * progress
        elif trend_peak <= i < trend_end:
            progress = (i - trend_peak) / (trend_end - trend_peak)
            cod_trend = 25 * (1 - progress)
        else:
            cod_trend = 0

        point = {"timestamp": timestamp.isoformat(), "pollutants": {}}
        anomalies = []

        for code, config in POLLUTANT_PROFILES.items():
            trend = cod_trend if code == "w01018" else 0
            value, flag = generate_value(config, trend)
            point["pollutants"][code] = {"value": value, "flag": flag}

            if flag == "B":
                anomalies.append(f"{config['name']}超标")

        # 随机异常
        if random.random() < 0.06:
            scenario = random.choice(ANOMALY_SCENARIOS)
            code = scenario["pollutant"]
            point["pollutants"][code] = {
                "value": scenario["value"] * random.uniform(0.95, 1.1),
                "flag": "B"
            }
            anomalies.append(scenario["name"])

        point["anomalies"] = anomalies
        data_points.append(point)

    # 显示数据摘要
    print(f"生成数据点: {len(data_points)} 个")
    print(f"污染物种类: {len(POLLUTANT_PROFILES)} 种")
    print(f"时间范围: {data_points[0]['timestamp']} ~ {data_points[-1]['timestamp']}")

    # 统计异常
    anomaly_count = sum(1 for p in data_points if p["anomalies"])
    print(f"异常数据点: {anomaly_count} 个")

    # 显示最新数据
    latest = data_points[-1]
    print("\n" + "-"*70)
    print("最新监测数据:")
    print("-"*70)

    # 常用指标
    print("\n【常用指标】")
    common_codes = ["w01018", "w21003", "w01001", "w21011", "w21001", "w01009"]
    for code in common_codes:
        if code in latest["pollutants"]:
            p = latest["pollutants"][code]
            config = POLLUTANT_PROFILES[code]
            flag_str = "✓" if p["flag"] == "N" else "⚠️超标"
            print(f"  {config['name']:8s}: {p['value']:10.4f}  {flag_str}")

    # 一类重金属
    print("\n【一类重金属】(毒性强)")
    class1_codes = ["w20111", "w20115", "w20117", "w20119", "w20120"]
    for code in class1_codes:
        if code in latest["pollutants"]:
            p = latest["pollutants"][code]
            config = POLLUTANT_PROFILES[code]
            flag_str = "✓" if p["flag"] == "N" else "⚠️超标"
            print(f"  {config['name']:8s}: {p['value']:10.6f}  {flag_str}")

    # 二类重金属
    print("\n【二类重金属】")
    class2_codes = ["w20121", "w20122", "w20123", "w20116", "w20124"]
    for code in class2_codes:
        if code in latest["pollutants"]:
            p = latest["pollutants"][code]
            config = POLLUTANT_PROFILES[code]
            flag_str = "✓" if p["flag"] == "N" else "⚠️超标"
            print(f"  {config['name']:8s}: {p['value']:10.4f}  {flag_str}")

    # 电镀特征
    print("\n【电镀特征污染物】")
    if "w21016" in latest["pollutants"]:
        p = latest["pollutants"]["w21016"]
        config = POLLUTANT_PROFILES["w21016"]
        flag_str = "✓" if p["flag"] == "N" else "⚠️超标"
        print(f"  {config['name']:8s}: {p['value']:10.4f}  {flag_str}")

    return data_points


async def send_to_backend(data_points: list):
    """通过TCP模拟发送数据到后端"""
    import socket

    print("\n" + "-"*70)
    print("正在向后端发送数据...")
    print("-"*70)

    # 构建HJ212格式数据包
    def build_hj212_packet(timestamp: datetime, pollutants: dict) -> str:
        """构建HJ212协议数据包"""
        # 数据段
        cp_parts = [f"DataTime={timestamp.strftime('%Y%m%d%H%M%S')}"]
        for code, data in pollutants.items():
            cp_parts.append(f"{code}-Rtd={data['value']:.6f},{code}-Flag={data['flag']}")

        cp = ";".join(cp_parts)

        # 完整数据段
        data_segment = f"QN={timestamp.strftime('%Y%m%d%H%M%S')}000;ST=32;CN=2011;PW=123456;MN={DEVICE_ID};Flag=4;CP=&&{cp}&&"

        # 计算CRC (简化版)
        crc = sum(ord(c) for c in data_segment) % 65536

        # 完整包
        packet = f"##{len(data_segment):04d}{data_segment}{crc:04X}\r\n"
        return packet

    try:
        # 连接TCP网关
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("localhost", 9880))
        print(f"  ✓ 已连接到TCP网关 (localhost:9880)")

        # 发送最近的数据点
        sent_count = 0
        for point in data_points[-20:]:  # 发送最近20个点
            timestamp = datetime.fromisoformat(point["timestamp"])
            packet = build_hj212_packet(timestamp, point["pollutants"])
            sock.send(packet.encode("utf-8"))
            sent_count += 1

            # 等待一小段时间
            await asyncio.sleep(0.1)

        print(f"  ✓ 已发送 {sent_count} 个数据包")
        sock.close()
        return True

    except Exception as e:
        print(f"  ✗ TCP连接失败: {e}")
        print("    (这在Mock模式下是正常的，数据已本地生成)")
        return False


async def main():
    # 生成数据
    data_points = await generate_and_display_data()

    # 尝试发送到后端
    await send_to_backend(data_points)

    print("\n" + "="*70)
    print("演示数据生成完成!")
    print("="*70)
    print("\n请刷新 Dashboard 查看以下功能:")
    print("  1. 实时监测数据卡片 - 显示17种污染物")
    print("  2. 重金属分类筛选 - 一类(5)/二类(5)/全部")
    print("  3. 趋势图 + AI预测 - COD有明显趋势变化")
    print("  4. AI智能诊断 - 分析异常数据")
    print("\n注意: Mock模式下数据在内存中，刷新后端会丢失")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
