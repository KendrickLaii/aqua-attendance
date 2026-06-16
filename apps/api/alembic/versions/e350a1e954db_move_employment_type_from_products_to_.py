"""Move employment_type from products to staff_profiles

Revision ID: e350a1e954db
Revises: 232b25394c0f
Create Date: 2026-06-16 12:55:57.114991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e350a1e954db'
down_revision: Union[str, None] = '232b25394c0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column to staff_profiles
    op.add_column('staff_profiles', sa.Column('employment_type', sa.String(length=20), nullable=True))

    # 2. Migrate existing data
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE staff_profiles
        SET employment_type = products.employment_type
        FROM products
        WHERE staff_profiles.id = products.id
        AND products.employment_type IS NOT NULL
    """))

    # 3. Drop old column from products
    op.drop_column('products', 'employment_type')


def downgrade() -> None:
    # 1. Add back to products
    op.add_column('products', sa.Column('employment_type', sa.String(length=20), nullable=True))

    # 2. Copy data back
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE products
        SET employment_type = staff_profiles.employment_type
        FROM staff_profiles
        WHERE products.id = staff_profiles.id
        AND staff_profiles.employment_type IS NOT NULL
    """))

    # 3. Drop from staff_profiles
    op.drop_column('staff_profiles', 'employment_type')
