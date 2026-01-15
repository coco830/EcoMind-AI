"""add_status_to_organizations

Revision ID: b8d5f2e7a3c9
Revises: 5b2c8e3f9a1d
Create Date: 2026-01-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d5f2e7a3c9'
down_revision: Union[str, Sequence[str], None] = '5b2c8e3f9a1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add status column to organizations table.

    This enables soft delete for organizations by setting status to 'inactive'
    when an invitation code is deleted, rather than hard deleting the organization.
    """
    # Add status column with default value 'active'
    op.add_column(
        'organizations',
        sa.Column('status', sa.String(20), nullable=False, server_default='active')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('organizations', 'status')
