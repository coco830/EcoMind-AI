"""add_org_id_to_invitation_codes

Revision ID: 400ae2b6ef5c
Revises: 4ad0a78051a6
Create Date: 2025-12-03 13:21:19.836508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '400ae2b6ef5c'
down_revision: Union[str, Sequence[str], None] = '4ad0a78051a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add org_id to invitation_codes."""
    # Add org_id column to invitation_codes
    op.add_column('invitation_codes', sa.Column('org_id', sa.VARCHAR(36), nullable=True))

    # Create foreign key constraint (SQLite limitations apply)
    # op.create_foreign_key('fk_invitation_org', 'invitation_codes', 'organizations', ['org_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('invitation_codes', 'org_id')
