"""add_password_reset_tokens_table

Revision ID: 5b2c8e3f9a1d
Revises: 400ae2b6ef5c
Create Date: 2025-12-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b2c8e3f9a1d'
down_revision: Union[str, Sequence[str], None] = '400ae2b6ef5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create password_reset_tokens table."""
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.VARCHAR(36), primary_key=True),
        sa.Column('user_id', sa.VARCHAR(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop password_reset_tokens table."""
    op.drop_table('password_reset_tokens')
