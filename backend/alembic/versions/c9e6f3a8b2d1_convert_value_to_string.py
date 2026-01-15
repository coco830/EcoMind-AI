"""convert_value_to_string

Revision ID: c9e6f3a8b2d1
Revises: b8d5f2e7a3c9
Create Date: 2026-01-12 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e6f3a8b2d1'
down_revision: Union[str, Sequence[str], None] = 'b8d5f2e7a3c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert value and standard_limit columns from Float to String.

    This allows storing scientific notation values like "4.0×102"
    for pollutants such as fecal coliform bacteria.
    """
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        inspector = sa.inspect(bind)
        if "self_inspection_data" not in inspector.get_table_names():
            return
        with op.batch_alter_table("self_inspection_data") as batch_op:
            batch_op.alter_column(
                "value",
                existing_type=sa.Float(),
                type_=sa.String(64),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "standard_limit",
                existing_type=sa.Float(),
                type_=sa.String(64),
                existing_nullable=True,
            )
        return

    # Convert value column from FLOAT to VARCHAR(64)
    # First cast existing float values to string
    op.alter_column(
        'self_inspection_data',
        'value',
        existing_type=sa.Float(),
        type_=sa.String(64),
        existing_nullable=False,
        postgresql_using='value::text'
    )

    # Convert standard_limit column from FLOAT to VARCHAR(64)
    op.alter_column(
        'self_inspection_data',
        'standard_limit',
        existing_type=sa.Float(),
        type_=sa.String(64),
        existing_nullable=True,
        postgresql_using='standard_limit::text'
    )


def downgrade() -> None:
    """Revert columns back to Float type.

    Note: This may fail if non-numeric values exist in the columns.
    """
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        inspector = sa.inspect(bind)
        if "self_inspection_data" not in inspector.get_table_names():
            return
        with op.batch_alter_table("self_inspection_data") as batch_op:
            batch_op.alter_column(
                "value",
                existing_type=sa.String(64),
                type_=sa.Float(),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "standard_limit",
                existing_type=sa.String(64),
                type_=sa.Float(),
                existing_nullable=True,
            )
        return

    op.alter_column(
        'self_inspection_data',
        'value',
        existing_type=sa.String(64),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using='value::float'
    )

    op.alter_column(
        'self_inspection_data',
        'standard_limit',
        existing_type=sa.String(64),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using='standard_limit::float'
    )
