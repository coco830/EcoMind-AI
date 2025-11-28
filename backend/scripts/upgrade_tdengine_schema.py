#!/usr/bin/env python3
"""
TDengine Schema Upgrade Script

升级 TDengine 数据库从窄表到宽表模式。
支持以下操作:
1. 创建新的宽表 meters_data
2. 动态添加新污染物列到现有表
3. 保留旧的窄表 monitoring_data 以便兼容

使用方法:
    python scripts/upgrade_tdengine_schema.py [--dry-run] [--add-columns]
"""

import asyncio
import argparse
import sys
sys.path.insert(0, '/home/candy/project/EcoMind-AI/backend')

from app.core.pollutant_library import POLLUTANT_MAP, get_all_pollutant_codes


def generate_create_table_sql() -> str:
    """生成创建宽表的 SQL 语句"""
    columns = []
    for code in POLLUTANT_MAP.keys():
        columns.append(f"    {code}_val DOUBLE")
        columns.append(f"    {code}_flag NCHAR(8)")

    columns_sql = ",\n".join(columns)

    sql = f"""
-- 创建宽表超级表 meters_data
-- 每条记录包含一个时间点的所有污染物数据
CREATE STABLE IF NOT EXISTS meters_data (
    ts TIMESTAMP,
    data_type NCHAR(16),
{columns_sql}
) TAGS (
    device_id NCHAR(64),
    org_id NCHAR(64)
);
"""
    return sql


def generate_alter_table_sql(new_codes: list[str]) -> list[str]:
    """生成动态添加列的 SQL 语句"""
    sqls = []
    for code in new_codes:
        sqls.append(f"ALTER STABLE meters_data ADD COLUMN {code}_val DOUBLE;")
        sqls.append(f"ALTER STABLE meters_data ADD COLUMN {code}_flag NCHAR(8);")
    return sqls


def generate_migration_sql() -> str:
    """生成完整的迁移 SQL 脚本"""
    create_sql = generate_create_table_sql()

    migration_sql = f"""
-- ============================================================================
-- TDengine 数据库迁移脚本
-- 从窄表 (monitoring_data) 升级到宽表 (meters_data)
-- 生成时间: {asyncio.get_event_loop().time() if False else 'N/A'}
-- 污染物数量: {len(POLLUTANT_MAP)}
-- ============================================================================

-- 确保数据库存在
CREATE DATABASE IF NOT EXISTS ecomind;
USE ecomind;

{create_sql}

-- 保留旧的窄表以便兼容
CREATE STABLE IF NOT EXISTS monitoring_data (
    ts TIMESTAMP,
    value DOUBLE,
    flag NCHAR(8),
    status INT
) TAGS (
    device_id NCHAR(64),
    pollutant_code NCHAR(32),
    org_id NCHAR(64)
);

-- ============================================================================
-- 说明：
-- 1. meters_data (宽表): 推荐用于新数据写入，每条记录包含所有指标
-- 2. monitoring_data (窄表): 保留用于向后兼容
-- ============================================================================
"""
    return migration_sql


def print_summary():
    """打印升级摘要"""
    print("=" * 70)
    print("TDengine Schema Upgrade Summary")
    print("=" * 70)
    print(f"Total pollutants defined: {len(POLLUTANT_MAP)}")
    print(f"Total columns (value + flag): {len(POLLUTANT_MAP) * 2}")
    print()
    print("Pollutant categories:")
    from app.core.pollutant_library import POLLUTANT_CATEGORIES
    for category, codes in POLLUTANT_CATEGORIES.items():
        print(f"  - {category}: {len(codes)} pollutants")
    print()
    print("Sample pollutants:")
    samples = [
        ("w01018", "化学需氧量"),
        ("w21003", "氨氮"),
        ("w20111", "总汞"),
        ("w20115", "总镉"),
    ]
    for code, name in samples:
        info = POLLUTANT_MAP.get(code, {})
        print(f"  - {code}: {name} ({info.get('unit', 'N/A')}, precision={info.get('precision', 'N/A')})")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Upgrade TDengine schema to wide table')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print SQL without executing')
    parser.add_argument('--output', type=str, default=None,
                       help='Output SQL to file')
    parser.add_argument('--add-columns', type=str, nargs='+',
                       help='Add new pollutant columns (e.g., w99001 w99002)')
    args = parser.parse_args()

    print_summary()

    if args.add_columns:
        print("\nGenerating ALTER TABLE statements for new columns...")
        sqls = generate_alter_table_sql(args.add_columns)
        for sql in sqls:
            print(sql)
    else:
        print("\nGenerating migration SQL...")
        sql = generate_migration_sql()

        if args.output:
            with open(args.output, 'w') as f:
                f.write(sql)
            print(f"SQL written to: {args.output}")
        else:
            print(sql)

    if args.dry_run:
        print("\n[DRY RUN] No changes were made to the database.")


if __name__ == '__main__':
    main()
