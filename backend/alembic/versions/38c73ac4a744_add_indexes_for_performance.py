"""add_indexes_for_performance

Revision ID: 38c73ac4a744
Revises:
Create Date: 2025-11-29 00:35:39.240674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38c73ac4a744'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add performance indexes.

    Note: ALTER COLUMN operations removed due to SQLite limitations.
    Indexes are the primary performance optimization for this migration.
    Using if_not_exists=True to handle partial migrations gracefully.
    """
    # Add alarm indexes for high-frequency query patterns
    op.create_index('ix_alarm_device_created', 'alarms', ['device_id', 'created_at'], unique=False, if_not_exists=True)
    op.create_index('ix_alarm_level', 'alarms', ['level'], unique=False, if_not_exists=True)
    op.create_index('ix_alarm_status', 'alarms', ['status'], unique=False, if_not_exists=True)
    op.create_index('ix_alarm_status_created', 'alarms', ['status', 'created_at'], unique=False, if_not_exists=True)

    # Add device indexes for high-frequency query patterns
    op.create_index('ix_device_created_at', 'devices', ['created_at'], unique=False, if_not_exists=True)
    op.create_index('ix_device_last_heartbeat', 'devices', ['last_heartbeat'], unique=False, if_not_exists=True)
    op.create_index('ix_device_org_id', 'devices', ['org_id'], unique=False, if_not_exists=True)
    op.create_index('ix_device_org_status', 'devices', ['org_id', 'status'], unique=False, if_not_exists=True)
    op.create_index('ix_device_status', 'devices', ['status'], unique=False, if_not_exists=True)


def downgrade() -> None:
    """Downgrade schema - remove performance indexes."""
    # Remove device indexes
    op.drop_index('ix_device_status', table_name='devices', if_exists=True)
    op.drop_index('ix_device_org_status', table_name='devices', if_exists=True)
    op.drop_index('ix_device_org_id', table_name='devices', if_exists=True)
    op.drop_index('ix_device_last_heartbeat', table_name='devices', if_exists=True)
    op.drop_index('ix_device_created_at', table_name='devices', if_exists=True)

    # Remove alarm indexes
    op.drop_index('ix_alarm_status_created', table_name='alarms', if_exists=True)
    op.drop_index('ix_alarm_status', table_name='alarms', if_exists=True)
    op.drop_index('ix_alarm_level', table_name='alarms', if_exists=True)
    op.drop_index('ix_alarm_device_created', table_name='alarms', if_exists=True)
