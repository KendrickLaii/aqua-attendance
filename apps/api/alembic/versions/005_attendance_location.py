"""Add location on attendance events and last_event_location on products."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attendance_events", sa.Column("location", sa.String(255), nullable=True))
    op.add_column("products", sa.Column("last_event_location", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "last_event_location")
    op.drop_column("attendance_events", "location")
