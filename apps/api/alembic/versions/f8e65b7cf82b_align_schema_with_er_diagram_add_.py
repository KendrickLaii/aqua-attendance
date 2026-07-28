"""align profile schema with units lifecycle dates

Revision ID: f8e65b7cf82b
Revises: 032
Create Date: 2026-07-28 15:53:43.665880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8e65b7cf82b'
down_revision: Union[str, None] = '032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-preserving renames and migrations before column drops
    # 1. Rename units.enrollment_date -> units.start_date (preserve data)
    op.alter_column('units', 'enrollment_date', new_column_name='start_date', existing_type=sa.Date(), existing_nullable=True)

    # 2. Copy existing profile lifecycle dates into units.start_date/exit_date before dropping profile columns.
    op.execute("""
        UPDATE units
        SET start_date = sp.hire_date,
            exit_date = sp.termination_date
        FROM staff_profiles sp
        WHERE units.id = sp.id
          AND units.unit_type = 'staff'
          AND (units.start_date IS NULL OR units.exit_date IS NULL)
    """)
    op.execute("""
        UPDATE units
        SET start_date = sp.enrollment_date,
            exit_date = sp.graduation_date
        FROM student_profiles sp
        WHERE units.id = sp.id
          AND units.unit_type = 'student'
          AND (units.start_date IS NULL OR units.exit_date IS NULL)
    """)

    # 3. Add gender/date_of_birth to profile tables and migrate from units.
    op.add_column('student_profiles', sa.Column('gender', sa.String(length=20), nullable=True))
    op.add_column('student_profiles', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('staff_profiles', sa.Column('gender', sa.String(length=20), nullable=True))
    op.add_column('staff_profiles', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.execute("""
        UPDATE student_profiles
        SET gender = u.gender,
            date_of_birth = u.date_of_birth
        FROM units u
        WHERE student_profiles.id = u.id
          AND u.unit_type = 'student'
    """)
    op.execute("""
        UPDATE staff_profiles
        SET gender = u.gender,
            date_of_birth = u.date_of_birth
        FROM units u
        WHERE staff_profiles.id = u.id
          AND u.unit_type = 'staff'
    """)

    # 4. Drop moved columns
    op.drop_column('units', 'gender')
    op.drop_column('units', 'date_of_birth')
    op.drop_column('staff_profiles', 'hire_date')
    op.drop_column('staff_profiles', 'termination_date')
    op.drop_column('student_profiles', 'enrollment_date')
    op.drop_column('student_profiles', 'graduation_date')

    # 5. Index adjustments (drop+recreate for renamed product → unit indexes)
    op.drop_index('ix_attendance_events_product_recorded', table_name='attendance_events')
    op.create_index('ix_attendance_events_unit_recorded', 'attendance_events', ['unit_id', 'recorded_at'], unique=False)
    op.drop_index('ix_unit_scan_locations_location_id', table_name='unit_scan_locations')
    op.drop_index('ix_products_code', table_name='units')
    op.create_index(op.f('ix_units_code'), 'units', ['code'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.add_column('student_profiles', sa.Column('graduation_date', sa.DATE(), autoincrement=False, nullable=True))
    op.add_column('student_profiles', sa.Column('enrollment_date', sa.DATE(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE student_profiles
        SET enrollment_date = u.start_date,
            graduation_date = u.exit_date
        FROM units u
        WHERE student_profiles.id = u.id
          AND u.unit_type = 'student'
    """)
    op.add_column('staff_profiles', sa.Column('termination_date', sa.DATE(), autoincrement=False, nullable=True))
    op.add_column('staff_profiles', sa.Column('hire_date', sa.DATE(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE staff_profiles
        SET hire_date = u.start_date,
            termination_date = u.exit_date
        FROM units u
        WHERE staff_profiles.id = u.id
          AND u.unit_type = 'staff'
    """)
    op.add_column('units', sa.Column('date_of_birth', sa.DATE(), autoincrement=False, nullable=True))
    op.add_column('units', sa.Column('gender', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    op.add_column('units', sa.Column('enrollment_date', sa.DATE(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE units
        SET gender = COALESCE(students.gender, staff.gender),
            date_of_birth = COALESCE(students.date_of_birth, staff.date_of_birth)
        FROM student_profiles students
        FULL OUTER JOIN staff_profiles staff ON staff.id = students.id
        WHERE units.id = COALESCE(students.id, staff.id)
    """)
    op.drop_index(op.f('ix_units_code'), table_name='units')
    op.create_index('ix_products_code', 'units', ['code'], unique=True)
    op.drop_column('units', 'start_date')
    op.create_index('ix_unit_scan_locations_location_id', 'unit_scan_locations', ['location_id'], unique=False)
    op.drop_column('student_profiles', 'date_of_birth')
    op.drop_column('student_profiles', 'gender')
    op.drop_column('staff_profiles', 'date_of_birth')
    op.drop_column('staff_profiles', 'gender')
    op.drop_index('ix_attendance_events_unit_recorded', table_name='attendance_events')
    op.create_index('ix_attendance_events_product_recorded', 'attendance_events', ['unit_id', 'recorded_at'], unique=False)
