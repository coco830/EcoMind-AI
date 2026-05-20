"""add cascade delete to device foreign keys

Revision ID: f3a7b9c1d2e4
Revises: d7f1c2b3a4e5
Create Date: 2026-02-26 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f3a7b9c1d2e4"
down_revision: Union[str, None] = "d7f1c2b3a4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # alarms.device_id -> devices.id  加上 ON DELETE CASCADE
    op.drop_constraint("alarms_ibfk_1", "alarms", type_="foreignkey")
    op.create_foreign_key(
        "alarms_ibfk_1", "alarms", "devices",
        ["device_id"], ["id"], ondelete="CASCADE",
    )

    # daily_reports.device_id -> devices.id  加上 ON DELETE CASCADE
    op.drop_constraint("daily_reports_ibfk_1", "daily_reports", type_="foreignkey")
    op.create_foreign_key(
        "daily_reports_ibfk_1", "daily_reports", "devices",
        ["device_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("alarms_ibfk_1", "alarms", type_="foreignkey")
    op.create_foreign_key(
        "alarms_ibfk_1", "alarms", "devices",
        ["device_id"], ["id"],
    )

    op.drop_constraint("daily_reports_ibfk_1", "daily_reports", type_="foreignkey")
    op.create_foreign_key(
        "daily_reports_ibfk_1", "daily_reports", "devices",
        ["device_id"], ["id"],
    )
