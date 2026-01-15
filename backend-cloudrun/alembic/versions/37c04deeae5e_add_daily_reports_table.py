"""add_daily_reports_table

Revision ID: 37c04deeae5e
Revises: e0b03fa03741
Create Date: 2025-12-01 19:33:07.929943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37c04deeae5e'
down_revision: Union[str, Sequence[str], None] = 'e0b03fa03741'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create daily_reports table
    op.create_table(
        'daily_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('device_id', sa.String(36), sa.ForeignKey('devices.id'), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(32), nullable=True, default='pending'),
        sa.Column('report_content', sa.Text(), nullable=True),
        sa.Column('stats_snapshot', sa.Text(), nullable=True),
        sa.Column('pollutant_count', sa.Integer(), nullable=True),
        sa.Column('data_points', sa.Integer(), nullable=True),
        sa.Column('domain', sa.String(32), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes
    op.create_index('ix_daily_report_device', 'daily_reports', ['device_id'])
    op.create_index('ix_daily_report_date', 'daily_reports', ['report_date'])
    op.create_index('ix_daily_report_status', 'daily_reports', ['status'])

    # Create unique constraint
    op.create_unique_constraint('uq_device_report_date', 'daily_reports', ['device_id', 'report_date'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('daily_reports')
