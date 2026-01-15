"""merge heads

Revision ID: 2db9405c55ae
Revises: a1b2c3d4e5f6, d7f1c2b3a4e5
Create Date: 2026-01-15 14:55:15.245433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2db9405c55ae'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'd7f1c2b3a4e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
