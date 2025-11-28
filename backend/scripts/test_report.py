#!/usr/bin/env python3
"""测试报表功能的脚本 - 生成测试数据并验证报表导出。"""

import asyncio
import os
import sys
import random
from datetime import datetime, timedelta
from uuid import uuid4

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置环境变量
os.environ["TDENGINE_MOCK"] = "true"


async def main():
    """主测试函数。"""
    from app.db.tdengine_client import get_tdengine_client
    from app.services.report_service import get_report_service

    print("=" * 60)
    print("报表功能测试脚本")
    print("=" * 60)

    # 获取 TDengine 客户端和报表服务
    tdengine = get_tdengine_client()
    report_service = get_report_service()

    # 测试设备信息
    device_id = "TEST_DEVICE_001"
    device_name = "测试水质监测站"
    org_id = "test-org-001"

    # 测试污染物列表（水质监测常见指标）
    pollutants = [
        ("w01018", "化学需氧量", 50.0, 200.0, 100.0),   # COD
        ("w01019", "氨氮", 0.5, 15.0, 8.0),              # 氨氮
        ("w01001", "pH值", 6.0, 9.0, None),              # pH
        ("w01010", "溶解氧", 3.0, 10.0, None),           # 溶解氧
        ("w21003", "总氮", 0.5, 20.0, 15.0),             # 总氮
    ]

    # 生成过去7天的测试数据
    print("\n[1] 生成测试数据...")
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)

    data_count = 0
    current_time = start_time

    while current_time < end_time:
        for code, name, min_val, max_val, threshold in pollutants:
            # 生成随机值
            value = random.uniform(min_val, max_val)

            # 有5%概率超标
            if threshold and random.random() < 0.05:
                value = threshold * random.uniform(1.1, 1.5)

            # 插入数据
            await tdengine.insert_monitoring_data(
                device_id=device_id,
                pollutant_code=code,
                org_id=org_id,
                timestamp=current_time,
                value=round(value, 4),
                flag="N",  # 正常数据
                status=0,
            )
            data_count += 1

        # 每分钟一条数据
        current_time += timedelta(minutes=1)

    print(f"    已生成 {data_count} 条测试数据")
    print(f"    时间范围: {start_time} 到 {end_time}")

    # 测试日报预览
    print("\n[2] 测试日报预览...")
    today = datetime.now().date()
    daily_stats = await report_service.generate_daily_report(
        device_id=device_id,
        device_name=device_name,
        report_date=today,
        thresholds={
            "w01018": 100.0,  # COD 阈值
            "w01019": 8.0,   # 氨氮阈值
            "w21003": 15.0,  # 总氮阈值
        }
    )

    print(f"    设备: {daily_stats['device_name']}")
    print(f"    周期: {daily_stats['period']['start'][:10]}")
    print(f"    总记录数: {daily_stats['summary']['total_records']}")
    print(f"    捕获率: {daily_stats['summary']['capture_rate']}%")
    print(f"    超标次数: {daily_stats['summary']['exceedance_count']}")
    print(f"    污染物统计:")
    for p in daily_stats['pollutants']:
        print(f"      - {p['pollutant_name']}: 平均={p['avg_value']:.2f}, 最大={p['max_value']:.2f}, 超标={p['exceedance_count']}次")

    # 测试月报预览
    print("\n[3] 测试月报预览...")
    monthly_stats = await report_service.generate_monthly_report(
        device_id=device_id,
        device_name=device_name,
        year=today.year,
        month=today.month,
        thresholds={
            "w01018": 100.0,
            "w01019": 8.0,
            "w21003": 15.0,
        }
    )

    print(f"    周期天数: {monthly_stats['period']['days']} 天")
    print(f"    总记录数: {monthly_stats['summary']['total_records']}")
    print(f"    捕获率: {monthly_stats['summary']['capture_rate']}%")

    # 测试 Excel 导出
    print("\n[4] 测试 Excel 导出...")
    excel_bytes = await report_service.generate_excel_report(
        device_id=device_id,
        device_name=device_name,
        start_time=datetime.combine(today, datetime.min.time()),
        end_time=datetime.now(),
        report_type="daily",
        thresholds={"w01018": 100.0, "w01019": 8.0, "w21003": 15.0}
    )

    # 保存 Excel 文件
    excel_path = "/tmp/test_report.xlsx"
    with open(excel_path, "wb") as f:
        f.write(excel_bytes)
    print(f"    Excel 文件已保存: {excel_path}")
    print(f"    文件大小: {len(excel_bytes)} bytes")

    # 测试 PDF 导出
    print("\n[5] 测试 PDF 导出...")
    pdf_bytes = await report_service.generate_pdf_report(
        device_id=device_id,
        device_name=device_name,
        start_time=datetime.combine(today, datetime.min.time()),
        end_time=datetime.now(),
        report_type="daily",
        thresholds={"w01018": 100.0, "w01019": 8.0, "w21003": 15.0}
    )

    # 保存 PDF 文件
    pdf_path = "/tmp/test_report.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"    PDF 文件已保存: {pdf_path}")
    print(f"    文件大小: {len(pdf_bytes)} bytes")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print(f"\n生成的文件:")
    print(f"  - Excel: {excel_path}")
    print(f"  - PDF: {pdf_path}")
    print("\n你可以打开这些文件查看报表效果。")


if __name__ == "__main__":
    asyncio.run(main())
