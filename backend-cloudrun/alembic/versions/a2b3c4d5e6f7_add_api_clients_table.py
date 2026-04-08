"""add api_clients table for openapi integrations

Revision ID: a2b3c4d5e6f7
Revises: f3a7b9c1d2e4
Create Date: 2026-03-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f3a7b9c1d2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_clients table for external agent integrations."""
    op.create_table(
        "api_clients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("api_key", sa.String(128), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("permissions", sa.Text(), nullable=True),
        sa.Column("rate_limit", sa.Integer(), nullable=False, default=60),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes
    op.create_index("ix_api_client_api_key", "api_clients", ["api_key"], unique=True)
    op.create_index("ix_api_client_org_id", "api_clients", ["org_id"])


def downgrade() -> None:
    """Drop api_clients table."""
    op.drop_table("api_clients")
