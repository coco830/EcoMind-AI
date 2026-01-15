"""add_regulator_scope_fields

Revision ID: d7f1c2b3a4e5
Revises: c9e6f3a8b2d1
Create Date: 2026-01-15 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7f1c2b3a4e5"
down_revision: Union[str, Sequence[str], None] = "c9e6f3a8b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add regulator scope fields."""
    op.add_column(
        "organizations",
        sa.Column("org_type", sa.String(32), nullable=False, server_default="enterprise"),
    )
    op.add_column("organizations", sa.Column("region_code", sa.String(64), nullable=True))
    op.add_column("organizations", sa.Column("region_name", sa.String(128), nullable=True))
    op.add_column("organizations", sa.Column("park_code", sa.String(64), nullable=True))
    op.add_column("organizations", sa.Column("park_name", sa.String(128), nullable=True))
    op.add_column("organizations", sa.Column("industry_type", sa.String(64), nullable=True))
    op.add_column("organizations", sa.Column("jurisdiction_level", sa.String(32), nullable=True))
    op.add_column("organizations", sa.Column("jurisdiction_codes", sa.Text(), nullable=True))

    op.add_column(
        "invitation_codes",
        sa.Column("org_type", sa.String(32), nullable=False, server_default="enterprise"),
    )
    op.add_column("invitation_codes", sa.Column("region_code", sa.String(64), nullable=True))
    op.add_column("invitation_codes", sa.Column("region_name", sa.String(128), nullable=True))
    op.add_column("invitation_codes", sa.Column("park_code", sa.String(64), nullable=True))
    op.add_column("invitation_codes", sa.Column("park_name", sa.String(128), nullable=True))
    op.add_column("invitation_codes", sa.Column("industry_type", sa.String(64), nullable=True))
    op.add_column("invitation_codes", sa.Column("jurisdiction_level", sa.String(32), nullable=True))
    op.add_column("invitation_codes", sa.Column("jurisdiction_codes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("invitation_codes", "jurisdiction_codes")
    op.drop_column("invitation_codes", "jurisdiction_level")
    op.drop_column("invitation_codes", "industry_type")
    op.drop_column("invitation_codes", "park_name")
    op.drop_column("invitation_codes", "park_code")
    op.drop_column("invitation_codes", "region_name")
    op.drop_column("invitation_codes", "region_code")
    op.drop_column("invitation_codes", "org_type")

    op.drop_column("organizations", "jurisdiction_codes")
    op.drop_column("organizations", "jurisdiction_level")
    op.drop_column("organizations", "industry_type")
    op.drop_column("organizations", "park_name")
    op.drop_column("organizations", "park_code")
    op.drop_column("organizations", "region_name")
    op.drop_column("organizations", "region_code")
    op.drop_column("organizations", "org_type")
