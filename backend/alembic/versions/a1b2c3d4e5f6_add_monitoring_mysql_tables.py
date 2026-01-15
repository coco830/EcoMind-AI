"""Add monitoring MySQL tables for time-series data storage

Revision ID: a1b2c3d4e5f6
Revises: e0b03fa03741
Create Date: 2025-12-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e0b03fa03741'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    # 创建原始监测数据表
    op.create_table(
        'monitoring_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.Column('device_id', sa.String(64), nullable=False),
        sa.Column('device_name', sa.String(128), nullable=True),
        sa.Column('org_id', sa.String(64), nullable=False),
        sa.Column('pollutant_code', sa.String(32), nullable=False),
        sa.Column('pollutant_name', sa.String(64), nullable=True),
        sa.Column('value', mysql.DOUBLE(), nullable=False),
        sa.Column('flag', sa.String(8), server_default='N'),
        sa.Column('status', sa.Integer(), server_default='0'),
        sa.Column('data_type', sa.String(16), server_default='realtime'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index('idx_monitoring_ts', 'monitoring_data', ['ts'])
    op.create_index('idx_monitoring_device', 'monitoring_data', ['device_id'])
    op.create_index('idx_monitoring_org', 'monitoring_data', ['org_id'])
    op.create_index('idx_monitoring_pollutant', 'monitoring_data', ['pollutant_code'])
    op.create_index('idx_monitoring_device_ts', 'monitoring_data', ['device_id', 'ts'])
    op.create_index('idx_monitoring_org_ts', 'monitoring_data', ['org_id', 'ts'])
    op.create_index('idx_monitoring_device_pollutant_ts', 'monitoring_data', ['device_id', 'pollutant_code', 'ts'])

    # 创建每日统计表
    op.create_table(
        'monitoring_daily_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stat_date', sa.Date(), nullable=False),
        sa.Column('device_id', sa.String(64), nullable=False),
        sa.Column('device_name', sa.String(128), nullable=True),
        sa.Column('org_id', sa.String(64), nullable=False),
        sa.Column('pollutant_code', sa.String(32), nullable=False),
        sa.Column('pollutant_name', sa.String(64), nullable=True),
        sa.Column('min_value', mysql.DOUBLE(), nullable=True),
        sa.Column('max_value', mysql.DOUBLE(), nullable=True),
        sa.Column('avg_value', mysql.DOUBLE(), nullable=True),
        sa.Column('sum_value', mysql.DOUBLE(), nullable=True),
        sa.Column('data_count', sa.Integer(), server_default='0'),
        sa.Column('exceed_count', sa.Integer(), server_default='0'),
        sa.Column('exceed_rate', sa.Float(), server_default='0'),
        sa.Column('valid_count', sa.Integer(), server_default='0'),
        sa.Column('invalid_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stat_date', 'device_id', 'pollutant_code', name='uq_daily_stats')
    )

    op.create_index('idx_daily_stats_date', 'monitoring_daily_stats', ['stat_date'])
    op.create_index('idx_daily_stats_device', 'monitoring_daily_stats', ['device_id'])
    op.create_index('idx_daily_stats_org', 'monitoring_daily_stats', ['org_id'])
    op.create_index('idx_daily_stats_org_date', 'monitoring_daily_stats', ['org_id', 'stat_date'])
    op.create_index('idx_daily_stats_device_date', 'monitoring_daily_stats', ['device_id', 'stat_date'])

    # 创建每小时统计表
    op.create_table(
        'monitoring_hourly_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('stat_hour', sa.DateTime(), nullable=False),
        sa.Column('device_id', sa.String(64), nullable=False),
        sa.Column('org_id', sa.String(64), nullable=False),
        sa.Column('pollutant_code', sa.String(32), nullable=False),
        sa.Column('min_value', mysql.DOUBLE(), nullable=True),
        sa.Column('max_value', mysql.DOUBLE(), nullable=True),
        sa.Column('avg_value', mysql.DOUBLE(), nullable=True),
        sa.Column('data_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stat_hour', 'device_id', 'pollutant_code', name='uq_hourly_stats')
    )

    op.create_index('idx_hourly_stats_hour', 'monitoring_hourly_stats', ['stat_hour'])
    op.create_index('idx_hourly_stats_device', 'monitoring_hourly_stats', ['device_id', 'stat_hour'])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.drop_table('monitoring_hourly_stats')
    op.drop_table('monitoring_daily_stats')
    op.drop_table('monitoring_data')
