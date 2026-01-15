"""add_industry_type_to_device

Revision ID: e0b03fa03741
Revises: 38c73ac4a744
Create Date: 2025-12-01 19:18:40.324941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0b03fa03741'
down_revision: Union[str, Sequence[str], None] = '38c73ac4a744'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add industry_type and national_standard columns to devices table
    op.add_column('devices', sa.Column('industry_type', sa.String(length=64), nullable=True))
    op.add_column('devices', sa.Column('national_standard', sa.String(length=128), nullable=True))
    op.create_index(op.f('ix_devices_industry_type'), 'devices', ['industry_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_devices_industry_type'), table_name='devices')
    op.drop_column('devices', 'national_standard')
    op.drop_column('devices', 'industry_type')
