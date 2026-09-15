"""add exercise difficult flag

Revision ID: 25d24ca4b7d1
Revises: 943cfa101009
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "25d24ca4b7d1"
down_revision: Union[str, Sequence[str], None] = "943cfa101009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("exercises") as batch_op:
        batch_op.add_column(sa.Column("is_difficult", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("exercises") as batch_op:
        batch_op.drop_column("is_difficult")

